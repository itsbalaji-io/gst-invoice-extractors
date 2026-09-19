#!/usr/bin/env python3
"""SpiceJet GST Invoice Extractor.
Extracts key fields from GST invoices (PDF) and writes to Excel.
Simplified, robust, minimal dependencies.
"""

import re
import os
import pandas as pd
import pdfplumber


def _text_from_pdf(pdf_path: str) -> str:
    """Return all text from PDF pages (PyMuPDF primary with pdfplumber fallback)."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() or "" for page in doc)
        doc.close()
        if text and len(text.strip()) > 30:
            return text
    except Exception:
        pass
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        return ""


def _first_match(patterns, text, flags=0):
    """Try a list of patterns, return first non-empty match group 1."""
    for pattern in patterns:
        m = re.search(pattern, text, flags)
        if m:
            return m.group(1).strip()
    return ""


def _last_match(pattern, text, flags=0):
    """Find all matches for pattern, return the last non-empty group 1."""
    matches = re.findall(pattern, text, flags)
    if matches:
        # Return the last match
        return matches[-1].strip()
    return ""


def extract_invoice_data(pdf_path: str) -> dict:
    text = _text_from_pdf(pdf_path)

    # Invoice Number: take the last match of "Invoice No:" to avoid picking "Original Invoice No"
    invoice_no_pattern = r"Invoice No[:\s]*([A-Z0-9\/]+)"
    invoice_no = _last_match(invoice_no_pattern, text, re.I)

    # Invoice Date: we want the date of the current invoice, not the original.
    # We'll look for "Invoice Date:" that is not preceded by "Original "
    # We'll use a similar approach: take the last match of "Invoice Date:"
    invoice_date_pattern = r"Invoice Date[:\s]*(\d{2}[^\d]*[A-Za-z]{3}[^\d]*\d{4}[^\d]*\d{1,2}[:]?\d{0,2}\s*[AP]M)"
    invoice_date = _last_match(invoice_date_pattern, text, re.I)

    # Supplier GSTIN
    supplier_gstin_patterns = [
        r"GSTIN of SpiceJet Limited\s*:\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])",
        r"GSTIN of SpiceJet Limited[:\s]*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])",
    ]
    supplier_gstin = _first_match(supplier_gstin_patterns, text, re.I)

    # Customer GSTIN
    customer_gstin_patterns = [
        r"GSTIN / UIN of Customer\s*:\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])",
        r"GSTN / UIN of Customer\s*:\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])",
        r"Customer.*?GSTIN[^\d]*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])",
    ]
    customer_gstin = _first_match(customer_gstin_patterns, text, re.I)

    # PNR
    pnr_patterns = [
        r"PNR:\s*([A-Z0-9]{6})",
        r"PNR[:\s]*([A-Z0-9]{6})",
    ]
    pnr = _first_match(pnr_patterns, text, re.I)

    # From and To: extract from the line containing PNR and Sector
    from_val = ""
    to_val = ""
    # Look for a line that has PNR and then Sector
    lines = text.split('\n')
    for line in lines:
        if "PNR:" in line and "Sector:" in line:
            # Pattern: PNR: ... Sector: <from> <separator> <to>
            # We'll try to capture two words after "Sector:" that are separated by non-alphanumeric
            match = re.search(r"Sect[oO]r:\s*([A-Za-z]+)\W+([A-Za-z]+)", line)
            if match:
                from_val = match.group(1)
                to_val = match.group(2)
                break

    # Voucher Type: look for TAX INVOICE or CREDIT NOTE
    voucher_type_patterns = [
        r"(TAX INVOICE|CREDIT NOTE)",
    ]
    voucher_type = _first_match(voucher_type_patterns, text, re.I)

    # Financials
    total_inv_patterns = [
        r"Total Invoice Value inclusive of Taxes \(in figures\)\s*([\d,]+\.?\d*)",
        r"Total Invoice Value[^\d]*([\d,]+\.?\d*)",
    ]
    total_gst_patterns = [
        r"Total GST\s*([\d,]+\.?\d*)",
        r"Total GST[^\d]*([\d,]+\.?\d*)",
    ]
    total_inv_str = _first_match(total_inv_patterns, text, re.I)
    total_gst_str = _first_match(total_gst_patterns, text, re.I)

    def to_float(s):
        try:
            return float(s.replace(',', '')) if s else 0.0
        except:
            return 0.0

    total_invoice_value = to_float(total_inv_str)
    total_gst = to_float(total_gst_str)
    taxable_value = total_invoice_value - total_gst if total_invoice_value and total_gst else 0.0

    # Try to extract tax amounts from the table
    # We'll look for lines that have a pattern of a percentage and an amount
    # and then try to assign to IGST, CGST, SGST based on nearby labels.
    igst_amount = 0.0
    cgst_amount = 0.0
    sgst_amount = 0.0

    # First, try to find labeled amounts
    lines = text.split('\n')
    for line in lines:
        # Look for patterns like: "2.50 % 139.00"
        matches = re.findall(r'(\d+\.\d+)\s*%\s*(\d+\.\d+)', line)
        for percent, amount in matches:
            amt = float(amount)
            if 'IGST' in line.upper():
                igst_amount += amt
            elif 'CGST' in line.upper():
                cgst_amount += amt
            elif 'SGST' in line.upper():
                sgst_amount += amt

    # If we didn't find any labels, we try to infer from the total_gst and the amounts we found
    if not (igst_amount or cgst_amount or sgst_amount):
        # Collect all amount matches from the entire text
        all_matches = re.findall(r'(\d+\.\d+)\s*%\s*(\d+\.\d+)', text)
        amounts = [float(amt) for _, amt in all_matches]
        if amounts:
            total_from_matches = sum(amounts)
            # If the sum of the amounts we found equals the total_gst (within 0.01)
            if abs(total_from_matches - total_gst) < 0.01:
                if len(amounts) == 2 and abs(amounts[0] - amounts[1]) < 0.01:
                    # Assume two equal amounts are CGST and SGST
                    cgst_amount = amounts[0]
                    sgst_amount = amounts[1]
                else:
                    # If not two equal amounts, we don't know, so put all in IGST as fallback
                    igst_amount = total_gst
            else:
                # The sums don't match, so we don't trust these amounts
                igst_amount = total_gst
        else:
            # No amounts found, assume all tax is IGST
            igst_amount = total_gst
    # If we found some labeled amounts, we trust them (even if they don't sum to total_gst, there might be rounding)

    # Prepare the result
    return {
        "file": pdf_path,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "supplier_gstin": supplier_gstin,
        "customer_gstin": customer_gstin,
        "pnr": pnr,
        "flight_no": "",  # Not found in SpiceJet invoices we saw
        "from": from_val,
        "to": to_val,
        "voucher_type": voucher_type,
        "taxable_value": f"{taxable_value:.2f}",
        "non_taxable_exempted": "0.00",
        "igst_amount": f"{igst_amount:.2f}",
        "cgst_amount": f"{cgst_amount:.2f}",
        "sgst_amount": f"{sgst_amount:.2f}",
        "grand_total": f"{total_invoice_value:.2f}",
    }


def main(source_dir=None):
    import sys
    if source_dir is None:
        if len(sys.argv) > 1:
            source_dir = sys.argv[1]
        elif os.path.isdir("SpiceJet"):
            source_dir = "SpiceJet"
        else:
            source_dir = "."
    pdf_files = [os.path.join(source_dir, f) for f in os.listdir(source_dir) if f.lower().endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDF files in {source_dir}")
    results = []
    for pdf in sorted(pdf_files):
        print(f"Processing {pdf}...")
        try:
            res = extract_invoice_data(pdf)
            # Only record if it has basic invoice data
            if res.get("invoice_no") or res.get("supplier_gstin"):
                results.append(res)
            else:
                print(f"  Skipped non-SpiceJet/unmatched file: {pdf}")
        except Exception as e:
            print(f"  Error on {pdf}: {e}")
    if results:
        df = pd.DataFrame(results)
        df.to_excel("spicejet_invoices_extracted.xlsx", index=False)
        print(f"Written {len(results)} records to spicejet_invoices_extracted.xlsx")
    else:
        print("No SpiceJet invoice data extracted.")


if __name__ == "__main__":
    main()