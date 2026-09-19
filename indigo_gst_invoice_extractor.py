#!/usr/bin/env python3
"""Indigo GST Invoice Extractor.
Extracts key fields from GST invoices (PDF) and writes to Excel.
Simplified, robust, minimal dependencies.
"""

import glob
import re
import pandas as pd
import pdfplumber


def _text_from_pdf(pdf_path: str) -> str:
    """Return all text from PDF pages concatenated with newlines."""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _first_match(pattern: str, text: str, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


def _is_valid_invoice(text: str) -> bool:
    """Check if the PDF text represents a valid GST invoice (not just an itinerary)."""
    # Must have a proper invoice number (not a GSTIN pattern)
    invoice_no_match = re.search(r"(?:Number|Original Invoice Number|Invoice No|Invoice Number)[:\s]*([A-Z0-9]{8,})", text, re.I)
    if not invoice_no_match:
        return False
    invoice_no = invoice_no_match.group(1)
    # Invoice numbers should NOT match GSTIN pattern (15 alphanumeric with specific format)
    if re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z]$", invoice_no):
        return False

    # Must have supplier GSTIN
    if not re.search(r"(?:GSTIN|GST)[:\s]*[A-Z0-9]{15}", text, re.I):
        return False

    # Must have either customer GSTIN or PNR
    has_customer_gstin = bool(re.search(r"GSTIN of Customer[:\s]*[A-Z0-9]{15}", text, re.I))
    has_pnr = bool(re.search(r"PNR[:\s]*[A-Z0-9]{6}", text, re.I))
    if not (has_customer_gstin or has_pnr):
        return False

    # Must have date
    if not re.search(r"Date[:\s]*[0-9]{1,2}\s*[A-Za-z]{3,}\s*[0-9]{4}", text, re.I):
        return False

    # Must have flight info (From/To)
    if not (re.search(r"From:\s*[A-Z]{3}", text, re.I) and re.search(r"To:\s*[A-Z]{3}", text, re.I)):
        return False

    return True


def extract_invoice_data(pdf_path: str) -> dict:
    text = _text_from_pdf(pdf_path)

    # Validate this is actually a GST invoice
    if not _is_valid_invoice(text):
        return {"file": pdf_path, "error": "Not a valid GST invoice"}
    # Invoice number: handle various formats like DL1252611CR37363, GA1262705AC42130, etc.
    invoice_no = _first_match(r"(?:Number|Original Invoice Number|Invoice No|Invoice Number)[:\s]*([A-Z0-9]{8,})", text, re.I)
    invoice_date = _first_match(r"Date[:\s]*([0-9]{1,2}\s*[A-Za-z]{3,}\s*[0-9]{4})", text, re.I)
    # GSTIN pattern: 15 alphanumeric chars (2 state + 10 PAN + 1 entity + 1 digit + 1 checksum)
    supplier_gstin = _first_match(r"(?:GSTIN|GST)[:\s]*([A-Z0-9]{15})", text, re.I)
    customer_gstin = _first_match(r"GSTIN of Customer[:\s]*([A-Z0-9]{15})", text, re.I)
    customer_name = _first_match(r"GSTIN Customer Name[:\s]*([^\n]+)", text, re.I)
    pnr = _first_match(r"PNR[:\s]*([A-Z0-9]{6})", text, re.I)
    flight_no = _first_match(r"Flight no[:\s]+([A-Z0-9\s\-]+?)\s+From", text, re.I)
    from_loc = _first_match(r"From:\s*([A-Z]+)", text, re.I)
    to_loc = _first_match(r"To:\s*([A-Z]+)", text, re.I)
    voucher_type = _first_match(r"(Tax Invoice|Credit Note|Debit Note|Revised Invoice|Supplementary Invoice|Bill of Supply|Delivery Challan|GST Credit Note)", text, re.I)

    # Tax breakup – try table first, fallback to regex
    taxable_value = non_taxable = igst_amt = cgst_amt = sgst_amt = grand_total = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        if not row:
                            continue
                        # Check for Grand Total row (summary row with different column structure)
                        if any('Grand Total' in str(cell) for cell in row if cell):
                            def _cell(i):
                                return row[i] if i < len(row) and row[i] else ""
                            # Grand Total row: 0='', 1='Grand Total', 2=Taxable, 3=NonTaxable,
                            # 5=IGST Amt, 7=CGST Amt, 9=SGST Amt, 11=Grand Total
                            taxable_value = _cell(2).strip()
                            non_taxable = _cell(3).strip()
                            igst_amt = _cell(5).strip()
                            cgst_amt = _cell(7).strip()
                            sgst_amt = _cell(9).strip()
                            grand_total = _cell(11).strip()
                        # Also check data rows for tax amounts (in case Grand Total row not found)
                        elif len(row) >= 12 and row[0] and 'Air Travel' in str(row[0]):
                            def _cell(i):
                                return row[i] if i < len(row) and row[i] else ""
                            # Data row: 2=Taxable, 3=NonTaxable, 6=IGST Amt, 8=CGST Amt, 10=SGST Amt, 11=Total
                            if not taxable_value:
                                taxable_value = _cell(2).strip()
                            if not non_taxable:
                                non_taxable = _cell(3).strip()
                            if not igst_amt:
                                igst_amt = _cell(6).strip()
                            if not cgst_amt:
                                cgst_amt = _cell(8).strip()
                            if not sgst_amt:
                                sgst_amt = _cell(10).strip()
    except Exception:
        pass

    if not grand_total:
        grand_total = _first_match(r"Grand Total[\s₹]*([0-9,]+(?:\.[0-9]+)?)", text, re.I)
    if not taxable_value:
        taxable_value = _first_match(r"Taxable\s+Value[\s:]*([0-9,]+\.?[0-9]*)", text, re.I)
    if not igst_amt:
        igst_amt = _first_match(r"IGST[\s:]*[0-9.]*\s*([0-9,]+\.?[0-9]*)", text, re.I)
    if not cgst_amt:
        cgst_amt = _first_match(r"CGST[\s:]*[0-9.]*\s*([0-9,]+\.?[0-9]*)", text, re.I)
    if not sgst_amt:
        sgst_amt = _first_match(r"SGST[\s:]*[0-9.]*\s*([0-9,]+\.?[0-9]*)", text, re.I)

    return {
        "file": pdf_path,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "supplier_gstin": supplier_gstin,
        "customer_gstin": customer_gstin,
        "customer_name": customer_name,
        "taxable_value": taxable_value,
        "non_taxable_exempted": non_taxable,
        "igst_amount": igst_amt,
        "cgst_amount": cgst_amt,
        "sgst_amount": sgst_amt,
        "grand_total": grand_total,
        "pnr": pnr,
        "flight_no": flight_no,
        "from": from_loc,
        "to": to_loc,
        "voucher_type": voucher_type,
    }


def main(source_dir=None):
    import sys
    import os
    if source_dir is None:
        if len(sys.argv) > 1:
            source_dir = sys.argv[1]
        elif os.path.isdir("Indigo"):
            source_dir = "Indigo"
        else:
            source_dir = "."
    pdf_files = [os.path.join(source_dir, f) for f in os.listdir(source_dir) if f.lower().endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDF files in {source_dir}")
    results = []
    valid_count = 0
    skipped_count = 0
    for pdf in sorted(pdf_files):
        print(f"Processing {pdf}…")
        try:
            result = extract_invoice_data(pdf)
            if "error" in result:
                skipped_count += 1
                print(f"  Skipped: {result['error']}")
            else:
                results.append(result)
                valid_count += 1
        except Exception as e:
            print(f"  Error on {pdf}: {e}")
    if results:
        df = pd.DataFrame(results)
        out_file = "indigo_invoices_extracted.xlsx"
        df.to_excel(out_file, index=False)
        print(f"Written {valid_count} valid invoice records to {out_file}")
        print(f"Skipped {skipped_count} non-invoice files")
    else:
        print("No valid invoice data extracted.")


if __name__ == "__main__":
    main()