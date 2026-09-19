#!/usr/bin/env python3
"""Air India Express GST Invoice Extractor for the new invoice format (Invoice - 072612B*)."""

import re
import os
import pandas as pd
import pdfplumber


def extract_invoice_data(pdf_path: str) -> dict:
    text = ""
    tables = []  # list of tables (list of list of strings)
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)

    # Initialize result
    result = {
        "file": pdf_path,
        "invoice_no": "",
        "invoice_date": "",
        "supplier_gstin": "",
        "customer_gstin": "",
        "pnr": "",
        "flight_no": "",
        "flight_date": "",
        "from": "",
        "to": "",
        "place_of_supply": "",
        "voucher_type": "",
        "passenger_name": "",
        "taxable_value": "0.00",
        "non_taxable_exempted": "0.00",
        "igst_amount": "0.00",
        "cgst_amount": "0.00",
        "sgst_amount": "0.00",
        "grand_total": "0.00",
    }

    # --- Basic fields ---
    inv_match = re.search(r"Invoice Number\s*[:]\s*([A-Z0-9]+)", text, re.I)
    if inv_match:
        result["invoice_no"] = inv_match.group(1).strip()
    date_match = re.search(r"(?:Invoice|Debit Note|Credit Note)\s*Date\s*[:]\s*(\d{2}[\/\-]\d{2}[\/\-]\d{4})", text, re.I)
    if date_match:
        dt = date_match.group(1).strip()
        parts = re.split(r'[\/\-]', dt)
        if len(parts) == 3:
            result["invoice_date"] = f"{parts[0]}-{parts[1]}-{parts[2]}"
        else:
            result["invoice_date"] = dt
    gstn_match = re.search(r"GSTIN\s*[:]\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])", text, re.I)
    if gstn_match:
        result["supplier_gstin"] = gstn_match.group(1).strip()
    cust_gstn_match = re.search(r"Customer GSTIN\s*[:]\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])", text, re.I)
    if cust_gstn_match:
        result["customer_gstin"] = cust_gstn_match.group(1).strip()
    pnr_match = re.search(r"PNR\s*[:]\s*([A-Z0-9]+)", text, re.I)
    if pnr_match:
        result["pnr"] = pnr_match.group(1).strip()
    flight_no_match = re.search(r"Flight No\s*[:]\s*(\d+)", text, re.I)
    if flight_no_match:
        result["flight_no"] = flight_no_match.group(1).strip()
    flight_date_match = re.search(r"Flight Date\s*[:]\s*(\d{2}-\d{2}-\d{4})", text, re.I)
    if flight_date_match:
        result["flight_date"] = flight_date_match.group(1).strip()
    from_match = re.search(r"Flight From\s*[:]\s*([A-Z]+)", text, re.I)
    if from_match:
        result["from"] = from_match.group(1).strip()
    to_match = re.search(r"Flight To\s*[:]\s*([A-Z]+)", text, re.I)
    if to_match:
        result["to"] = to_match.group(1).strip()
    pos_match = re.search(r"Place of Supply\s*[:]\s*([A-Z\s]+)", text, re.I)
    if pos_match:
        place = pos_match.group(1).strip()
        code_match = re.search(r"\[(\d{2})\]", text)
        if code_match:
            result["place_of_supply"] = f"{place} [{code_match.group(1)}]"
        else:
            result["place_of_supply"] = place
    voucher_patterns = [
        r"(TAX INVOICE)",
        r"(CREDIT NOTE)",
        r"(DEBIT NOTE)",
        r"(BILL OF SUPPLY)",
        r"(REVISED INVOICE)",
        r"(SUPPLEMENTARY INVOICE)",
    ]
    for pat in voucher_patterns:
        m = re.search(pat, text, re.I)
        if m:
            result["voucher_type"] = m.group(1).upper()
            break
    lines = text.split('\n')
    for line in lines:
        if "Passenger Name" in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                name = parts[1].strip()
                name = name.split('\n')[0].strip()
                result["passenger_name"] = name
                break

    # --- Financials: extract from table ---
    def to_number(s):
        if not isinstance(s, str):
            return None
        s = s.strip()
        if not s:
            return None
        s = s.replace(',', '')
        try:
            return float(s)
        except:
            return None

    # Helper to clean cell text for header matching
    def clean_cell(cell):
        if cell is None:
            return ""
        # Replace newline with space and strip
        return str(cell).replace('\n', ' ').strip()

    # We'll look for a table that has the expected columns.
    for table in tables:
        if not table or len(table) < 3:
            continue
        first_row = table[0]
        second_row = table[1] if len(table) > 1 else []
        # Flatten first two rows to detect headers, cleaning newlines
        header_candidates = []
        max_len = max(len(first_row), len(second_row))
        for col in range(max_len):
            val1 = clean_cell(first_row[col] if col < len(first_row) else None)
            val2 = clean_cell(second_row[col] if col < len(second_row) else None)
            combined = f"{val1} {val2}".strip()
            header_candidates.append(combined)
        header_str = " ".join(header_candidates).upper()
        if "VALUE OF SERVICE" in header_str and "OTHER TAXES" in header_str:
            # This looks like our target table.
            col_map = {}
            for idx, header in enumerate(header_candidates):
                up = header.upper()
                if "VALUE OF SERVICE" in up:
                    col_map['value_of_service'] = idx
                elif "TAXABLE*" in up:
                    col_map['taxable_star'] = idx
                elif "NON TAXABLE*" in up:
                    col_map['non_taxable_star'] = idx
                elif "DISCOUNT" in up:
                    col_map['discount'] = idx
                elif "NET TAXABLE VALUE" in up:
                    col_map['net_taxable_value'] = idx
                elif "GST %" in up:
                    col_map['gst_percent'] = idx
                elif "CGST" in up:
                    col_map['cgst_percent'] = idx
                elif "SGST" in up or "UTGST" in up:
                    col_map['sgst_percent'] = idx
                elif "IGST" in up:
                    col_map['igst_percent'] = idx
                elif "TOTAL VALUE" in up:
                    col_map['total_value'] = idx

            # Data row is likely at index 2 (if present)
            data_row_idx = 2
            if data_row_idx < len(table):
                row = table[data_row_idx]
                def get_val(col_name):
                    idx = col_map.get(col_name)
                    if idx is not None and idx < len(row):
                        return to_number(row[idx])
                    return None

                # Taxable value = value of service + taxable*
                val_service = get_val('value_of_service')
                taxable_star = get_val('taxable_star')
                taxable_val = None
                if val_service is not None:
                    taxable_val = val_service
                    if taxable_star is not None:
                        taxable_val += taxable_star
                if taxable_val is not None:
                    result["taxable_value"] = f"{max(0.0, taxable_val):.2f}"

                # Non-taxable exempted = non taxable*
                non_taxable_val = get_val('non_taxable_star')
                if non_taxable_val is not None:
                    result["non_taxable_exempted"] = f"{max(0.0, non_taxable_val):.2f}"

                # Tax amounts: CGST, SGST, IGST from their respective columns
                cgst_amt = get_val('cgst_percent')
                if cgst_amt is not None:
                    result["cgst_amount"] = f"{max(0.0, cgst_amt):.2f}"
                sgst_amt = get_val('sgst_percent')
                if sgst_amt is not None:
                    result["sgst_amount"] = f"{max(0.0, sgst_amt):.2f}"
                igst_amt = get_val('igst_percent')
                if igst_amt is not None:
                    result["igst_amount"] = f"{max(0.0, igst_amt):.2f}"

                # Total value
                total_val = get_val('total_value')
                if total_val is not None:
                    result["grand_total"] = f"{max(0.0, total_val):.2f}"

                # If we got some values, break
                if (result["taxable_value"] != "0.00" or result["non_taxable_exempted"] != "0.00" or
                    result["igst_amount"] != "0.00" or result["cgst_amount"] != "0.00" or
                    result["sgst_amount"] != "0.00" or result["grand_total"] != "0.00"):
                    break
            else:
                # If row 2 doesn't exist, try to find a data row where first cell is numeric
                for r in range(len(table)):
                    row = table[r]
                    if not row:
                        continue
                    first_cell = row[0] if len(row) > 0 else ""
                    if isinstance(first_cell, str) and first_cell.strip().isdigit():
                        def get_val_from_row(r_idx, col_name):
                            idx = col_map.get(col_name)
                            if idx is not None and idx < len(row):
                                return to_number(row[idx])
                            return None
                        val_service = get_val_from_row(r, 'value_of_service')
                        taxable_star = get_val_from_row(r, 'taxable_star')
                        taxable_val = None
                        if val_service is not None:
                            taxable_val = val_service
                            if taxable_star is not None:
                                taxable_val += taxable_star
                        if taxable_val is not None:
                            result["taxable_value"] = f"{max(0.0, taxable_val):.2f}"
                        non_taxable_val = get_val_from_row(r, 'non_taxable_star')
                        if non_taxable_val is not None:
                            result["non_taxable_exempted"] = f"{max(0.0, non_taxable_val):.2f}"
                        cgst_amt = get_val_from_row(r, 'cgst_percent')
                        if cgst_amt is not None:
                            result["cgst_amount"] = f"{max(0.0, cgst_amt):.2f}"
                        sgst_amt = get_val_from_row(r, 'sgst_percent')
                        if sgst_amt is not None:
                            result["sgst_amount"] = f"{max(0.0, sgst_amt):.2f}"
                        igst_amt = get_val_from_row(r, 'igst_percent')
                        if igst_amt is not None:
                            result["igst_amount"] = f"{max(0.0, igst_amt):.2f}"
                        total_val = get_val_from_row(r, 'total_value')
                        if total_val is not None:
                            result["grand_total"] = f"{max(0.0, total_val):.2f}"
                        if (result["taxable_value"] != "0.00" or result["non_taxable_exempted"] != "0.00" or
                            result["igst_amount"] != "0.00" or result["cgst_amount"] != "0.00" or
                            result["sgst_amount"] != "0.00" or result["grand_total"] != "0.00"):
                            break

    # If still zero, fallback to label-based extraction
    if (result["taxable_value"] == "0.00" and result["non_taxable_exempted"] == "0.00" and
        result["igst_amount"] == "0.00" and result["cgst_amount"] == "0.00" and
        result["sgst_amount"] == "0.00" and result["grand_total"] == "0.00"):
        def get_amount_after_label(label, skip_sac=True):
            pattern = re.compile(r'{}\D*(\d[\d,]*(?:\.\d+)?)'.format(re.escape(label)), re.I)
            matches = list(pattern.finditer(text))
            if not matches:
                return 0.0
            for m in reversed(matches):
                val_str = m.group(1).replace(',', '')
                try:
                    val = float(val_str)
                    if skip_sac and val.is_integer() and 100000 <= val <= 999999:
                        continue
                    return val
                except:
                    pass
            return 0.0

        def get_tax_amount_after_rate(text, tax_label):
            pattern = re.compile(r'{}\D*(\d+\.\d+\s*%\s*)\D*(\d[\d,]*(?:\.\d+)?)'.format(re.escape(tax_label)), re.I)
            match = pattern.search(text)
            if match:
                num_str = match.group(2).replace(',', '')
                try:
                    return float(num_str)
                except:
                    pass
            return get_amount_after_label(tax_label, skip_sac=True)

        taxable = get_amount_after_label("Taxable Value")
        non_taxable = get_amount_after_label("Non Taxable Value")
        cgst = get_tax_amount_after_rate(text, "CGST")
        sgst = get_tax_amount_after_rate(text, "SGST")
        igst = get_tax_amount_after_rate(text, "IGST")
        gt = get_amount_after_label("Grand Total", skip_sac=False)
        if gt == 0.0:
            gt = get_amount_after_label("Total Invoice Value", skip_sac=False)
        if gt == 0.0:
            gt = get_amount_after_label("Total", skip_sac=False)
        if gt == 0.0:
            for line in lines:
                if "Grand Total" in line:
                    nums = []
                    for part in re.findall(r'-?\d[\d,]*\.?\d*', line):
                        num = to_number(part)
                        if num is not None:
                            nums.append(num)
                    if nums:
                        gt = nums[-1]
                        break
        result["taxable_value"] = f"{max(0.0, taxable):.2f}"
        result["non_taxable_exempted"] = f"{max(0.0, non_taxable):.2f}"
        result["cgst_amount"] = f"{max(0.0, cgst):.2f}"
        result["sgst_amount"] = f"{max(0.0, sgst):.2f}"
        result["igst_amount"] = f"{max(0.0, igst):.2f}"
        result["grand_total"] = f"{max(0.0, gt):.2f}"

    return result


def main(source_dir=None):
    import sys
    if source_dir is None:
        if len(sys.argv) > 1:
            source_dir = sys.argv[1]
        elif os.path.isdir('Air_India'):
            source_dir = 'Air_India'
        else:
            source_dir = '.'
    pdf_files = [os.path.join(source_dir, f) for f in os.listdir(source_dir) if f.lower().endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDF files in {source_dir}")
    results = []
    for pdf in sorted(pdf_files):
        print(f"Processing {pdf}...")
        try:
            results.append(extract_invoice_data(pdf))
        except Exception as e:
            print(f"  Error on {pdf}: {e}")
    if results:
        df = pd.DataFrame(results)
        cols = ["file", "invoice_no", "invoice_date", "supplier_gstin", "customer_gstin",
                "pnr", "flight_no", "flight_date", "from", "to", "place_of_supply",
                "voucher_type", "passenger_name",
                "taxable_value", "non_taxable_exempted", "igst_amount", "cgst_amount", "sgst_amount", "grand_total"]
        df = df[cols]
        output_file = "airindia_invoices_extracted.xlsx"
        df.to_excel(output_file, index=False)
        print(f"Written {len(results)} records to {output_file}")
        print(df.to_string())
    else:
        print("No data extracted.")


if __name__ == "__main__":
    main()


