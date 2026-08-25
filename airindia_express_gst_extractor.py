#!/usr/bin/env python3
"""Air India Express GST Invoice Extractor using table extraction for financials.
"""

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
    date_match = re.search(r"Invoice Date\s*[:]\s*(\d{2}-\d{2}-\d{4})", text, re.I)
    if date_match:
        result["invoice_date"] = date_match.group(1).strip()
    gstn_match = re.search(r"GSTN\s*[:]\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])", text, re.I)
    if gstn_match:
        result["supplier_gstin"] = gstn_match.group(1).strip()
    cust_gstn_match = re.search(r"GSTIN of Customer\s*[:]\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9][A-Z][0-9A-Z])", text, re.I)
    if cust_gstn_match:
        result["customer_gstin"] = cust_gstn_match.group(1).strip()
    pnr_match = re.search(r"PNR No\s*[:]\s*([A-Z0-9]+)", text, re.I)
    if pnr_match:
        result["pnr"] = pnr_match.group(1).strip()
    flight_no_match = re.search(r"Flight No\s*[:]\s*(\d+)", text, re.I)
    if flight_no_match:
        result["flight_no"] = flight_no_match.group(1).strip()
    flight_date_match = re.search(r"Flight Date\s*[:]\s*(\d{2}-\d{2}-\d{4})", text, re.I)
    if flight_date_match:
        result["flight_date"] = flight_date_match.group(1).strip()
    flight_from_match = re.search(r"Flight From\s*[:]\s*([A-Z]+)", text, re.I)
    if flight_from_match:
        result["from"] = flight_from_match.group(1).strip()
    flight_to_match = re.search(r"Flight To\s*[:]\s*([A-Z]+)", text, re.I)
    if flight_to_match:
        result["to"] = flight_to_match.group(1).strip()
    pos_match = re.search(r"Place of Supply\s*[:]\s*([A-Z\s]+)\s*\[(\d{2})\]", text, re.I)
    if pos_match:
        result["place_of_supply"] = f"{pos_match.group(1).strip()} [{pos_match.group(2)}]"
    else:
        pos_match2 = re.search(r"Place of Supply\s*[:]\s*([A-Z\s]+)", text, re.I)
        if pos_match2:
            result["place_of_supply"] = pos_match2.group(1).strip()

    # --- Voucher type ---
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

    # --- Passenger name ---
    lines = text.split('\n')
    for line in lines:
        if "Postal" in line:
            pass
        if "Passenger Name" in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                name = parts[1].strip()
                name = name.split('\n')[0].strip()
                result["passenger_name"] = name
                break

    # --- Financials: try to extract from tables ---
    def is_sac_code(val: float) -> bool:
        """Return True if value looks like a SAC code (6-digit integer)."""
        return val.is_integer() and 100000 <= val <= 999999

    def to_number(s):
        """Convert string to float, returning None if not a number."""
        if not isinstance(s, str):
            return None
        s = s.strip()
        if not s:
            return None
        # Remove commas
        s = s.replace(',', '')
        try:
            return float(s)
        except:
            return None

    # Initialize financial values
    taxable = 0.0
    non_taxable = 0.0
    igst = 0.0
    cgst = 0.0
    sgst = 0.0
    grand_total = 0.0

    # Process tables
    for table in tables:
        if not table or len(table) < 3:
            continue
        # Find the header row: first column contains 'Description', second contains 'SAC Code'
        header_row_idx = None
        for i, row in enumerate(table):
            if not row:
                continue
            if len(row) > 0 and isinstance(row[0], str) and 'Description' in row[0]:
                if len(row) > 1 and isinstance(row[1], str) and 'SAC Code' in row[1]:
                    header_row_idx = i
                    break
        if header_row_idx is None:
            # Try to find any row with 'Description' in first column
            for i, row in enumerate(table):
                if not row:
                    continue
                if len(row) > 0 and isinstance(row[0], str) and 'Description' in row[0]:
                    header_row_idx = i
                    break
        if header_row_idx is None:
            continue

        # We need at least two rows after the header for the rate/amount rows
        if len(table) < header_row_idx + 3:
            continue

        # Determine column indices for taxable and non-taxable from the header row
        tax_col_idx = None
        non_tax_col_idx = None
        # We'll also collect tax type info: list of (tax_type, amount_col_idx)
        tax_info = []  # each element is (tax_type, amount_col_idx)

        # Scan the header row for taxable and non-taxable
        for j, cell in enumerate(table[header_row_idx]):
            if not isinstance(cell, str):
                continue
            cell_upper = cell.upper()
            # Taxable Value column: contains TAXABLE and VALUE but not NON
            if 'TAXABLE' in cell_upper and 'VALUE' in cell_upper and 'NON' not in cell_upper:
                tax_col_idx = j
            # Non Taxable Value column: contains NON, TAXABLE, and VALUE
            if 'NON' in cell_upper and 'TAXABLE' in cell_upper and 'VALUE' in cell_upper:
                non_tax_col_idx = j

        # Now, look at the row after the header (header_row_idx+1) to find 'Rate (%)'
        # and the row after that (header_row_idx+2) to confirm it's the amount row? Actually, we don't need the second row.
        # We know that the amount column is the column after the 'Rate (%)' column.
        rate_row_idx = header_row_idx + 1
        if rate_row_idx >= len(table):
            continue
        rate_row = table[rate_row_idx]
        for j, cell in enumerate(rate_row):
            if not isinstance(cell, str):
                continue
            if 'Rate (%)' in cell:
                # The tax type is in the header row at the same column
                if j < len(table[header_row_idx]):
                    tax_type_cell = table[header_row_idx][j]
                    tax_type = None
                    if isinstance(tax_type_cell, str):
                        t = tax_type_cell.upper()
                        if 'CGST' in t:
                            tax_type = 'CGST'
                        elif 'SGST' in t:
                            tax_type = 'SGST'
                        elif 'IGST' in t:
                            tax_type = 'IGST'
                    # The amount column is the next column (j+1)
                    amount_col_idx = j + 1
                    if amount_col_idx < len(table[0]):  # ensure we have at least that many columns
                        tax_info.append((tax_type, amount_col_idx))

        # If we didn't find any tax info, try to look for 'Amount' in the header row? (fallback)
        if not tax_info:
            # As a fallback, look for columns that have 'Amount' in the header row
            for j, cell in enumerate(table[header_row_idx]):
                if not isinstance(cell, str):
                    continue
                if 'AMOUNT' in cell.upper():
                    # We don't know the tax type, but we can try to infer from the column name
                    # For simplicity, we'll skip and rely on the label-based fallback later.
                    pass

        # If we still don't have taxable and non-taxable columns, try to find them by looking for 'Total' and then assuming the previous two?
        # But let's just use the label-based fallback if we didn't find the columns.
        if tax_col_idx is None or non_tax_col_idx is None:
            # We'll skip this table and rely on the label-based fallback
            continue

        # Now, determine the data rows: start after the header and the two rows after (rate and amount rows)
        # But note: the structure might be header, then rate row, then amount row, then data.
        # Or it might be header, then rate/amount combined in one row? We've seen both.
        # Actually, in the examples we have:
        #   header row
        #   row with 'Rate (%)' and 'Amount' (two columns per tax)
        #   row with '' and '(Rs.)' (or empty) - this is the unit row
        #   then data rows
        # So we skip 3 rows: header, rate row, unit row.
        data_start_idx = header_row_idx + 3
        if data_start_idx >= len(table):
            # Maybe there is no unit row? Try skipping only 2 rows.
            data_start_idx = header_row_idx + 2
        if data_start_idx >= len(table):
            # Try skipping only 1 row.
            data_start_idx = header_row_idx + 1
        if data_start_idx >= len(table):
            continue

        # Process data rows until we hit an empty row or a row with 'Grand Total' in the first column
        for r in range(data_start_idx, len(table)):
            row = table[r]
            if not row:
                continue
            # Skip empty rows (all empty strings)
            if all(not isinstance(cell, str) or cell.strip() == '' for cell in row):
                continue
            # Stop if we hit the grand total row
            if len(row) > 0 and isinstance(row[0], str) and 'Grand Total' in row[0]:
                break

            # Extract taxable and non-taxable
            def safe_get(col_idx):
                if col_idx < len(row):
                    return to_number(row[col_idx])
                return None

            if tax_col_idx is not None and tax_col_idx < len(row):
                t_val = safe_get(tax_col_idx)
                if t_val is not None and not is_sac_code(t_val):
                    taxable += t_val
            if non_tax_col_idx is not None and non_tax_col_idx < len(row):
                nt_val = safe_get(non_tax_col_idx)
                if nt_val is not None and not is_sac_code(nt_val):
                    non_taxable += nt_val

            # Extract tax amounts
            for tax_type, amount_col_idx in tax_info:
                if amount_col_idx is not None and amount_col_idx < len(row):
                    tax_val = safe_get(amount_col_idx)
                    if tax_val is not None and not is_sac_code(tax_val):
                        if tax_type == 'CGST':
                            cgst += tax_val
                        elif tax_type == 'SGST':
                            sgst += tax_val
                        elif tax_type == 'IGST':
                            igst += tax_val

            # We could also try to get the grand total from the last column, but we'll compute it from the sum.

        # After processing all data rows in this table, compute the grand total from the summed components
        computed_grand_total = taxable + non_taxable + cgst + sgst + igst
        if computed_grand_total > 0:
            # We have a valid total from the table, so we can set grand_total and break
            grand_total = computed_grand_total
            break

    # If we didn't get any values from tables, fallback to label-based extraction
    if taxable == 0.0 and non_taxable == 0.0 and cgst == 0.0 and sgst == 0.0 and igst == 0.0:
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
            # Try to find pattern: label ... rate ... amount
            pattern = re.compile(r'{}\D*(\d+\.\d+\s*%\s*)\D*(\d[\d,]*(?:\.\d+)?)'.format(re.escape(tax_label)), re.I)
            match = pattern.search(text)
            if match:
                num_str = match.group(2).replace(',', '')
                try:
                    return float(num_str)
                except:
                    pass
            # Fallback to first number after label
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
        # Try to get from the line that contains "Grand Total" and capture the last number
        if gt == 0.0:
            for line in lines:
                if "Grand Total" in line:
                    nums = []
                    for part in re.findall(r'-?\d[\d,]*\.?\d*', line):
                        num = to_number(part)
                        if num is not None and not is_sac_code(num):
                            nums.append(num)
                    if nums:
                        gt = nums[-1]
                        break
        grand_total = gt

    # If we have taxable and non_taxable but no tax amounts, compute tax from grand_total
    if (cgst == 0.0 and sgst == 0.0 and igst == 0.0) and (taxable > 0 or non_taxable > 0) and grand_total > 0:
        total_tax = max(0.0, grand_total - taxable - non_taxable)
        # Determine tax type based on state codes
        supplier_state = result["supplier_gstin"][:2] if result["supplier_gstin"] else ""
        place_state = ""
        if "[" in result["place_of_supply"] and "]" in result["place_of_supply"]:
            place_state = result["place_of_supply"].split("[")[1].split("]")[0]
        else:
            m = re.search(r'\[(\d{2})\]', result["place_of_supply"])
            if m:
                place_state = m.group(1)
        if supplier_state == place_state and supplier_state != "" and place_state != "":
            # Intra-state: split equally
            cgst = total_tax / 2.0
            sgst = total_tax / 2.0
            igst = 0.0
        else:
            # Inter-state: all IGST
            igst = total_tax
            cgst = 0.0
            sgst = 0.0

    # If we have some tax amounts but the total doesn't match, adjust to match grand_total
    if grand_total > 0:
        total_tax = cgst + sgst + igst
        computed_total = taxable + non_taxable + total_tax
        if abs(computed_total - grand_total) > 0.01:
            # Adjust tax to match grand total
            total_tax_needed = max(0.0, grand_total - taxable - non_taxable)
            if total_tax_needed < 0:
                total_tax_needed = 0.0
            if cgst + sgst + igst > 0:
                # Scale existing taxes
                current_sum = cgst + sgst + igst
                if current_sum > 0:
                    scale = total_tax_needed / current_sum
                    cgst *= scale
                    sgst *= scale
                    igst *= scale
                else:
                    # No tax detected, assign based on state
                    supplier_state = result["supplier_gstin"][:2] if result["supplier_gstin"] else ""
                    place_state = ""
                    if "[" in result["place_of_supply"] and "]" in result["place_of_supply"]:
                        place_state = result["place_of_supply"].split("[")[1].split("]")[0]
                    else:
                        m = re.search(r'\[(\d{2})\]', result["place_of_supply"])
                        if m:
                            place_state = m.group(1)
                    if supplier_state == place_state and supplier_state != "" and place_state != "":
                        cgst = total_tax_needed / 2.0
                        sgst = total_tax_needed / 2.0
                        igst = 0.0
                    else:
                        igst = total_tax_needed
                        cgst = 0.0
                        sgst = 0.0
            else:
                # No tax detected, assign based on state
                supplier_state = result["supplier_gstin"][:2] if result["supplier_gstin"] else ""
                place_state = ""
                if "[" in result["place_of_supply"] and "]" in result["place_of_supply"]:
                    place_state = result["place_of_supply"].split("[")[1].split("]")[0]
                else:
                    m = re.search(r'\[(\d{2})\]', result["place_of_supply"])
                    if m:
                        place_state = m.group(1)
                if supplier_state == place_state and supplier_state != "" and place_state != "":
                    cgst = total_tax_needed / 2.0
                    sgst = total_tax_needed / 2.0
                    igst = 0.0
                else:
                    igst = total_tax_needed
                    cgst = 0.0
                    sgst = 0.0
            # Recompute
            total_tax = cgst + sgst + igst
            computed_total = taxable + non_taxable + total_tax
            if computed_total > 0:
                grand_total = computed_total
            else:
                # If computed_total is zero or negative, keep the original grand_total (which might be zero)
                # But we don't want to lower it, so we take the max.
                grand_total = max(grand_total, computed_total)

    # Format results
    result["taxable_value"] = f"{max(0.0, taxable):.2f}"
    result["non_taxable_exempted"] = f"{max(0.0, non_taxable):.2f}"
    result["cgst_amount"] = f"{max(0.0, cgst):.2f}"
    result["sgst_amount"] = f"{max(0.0, sgst):.2f}"
    result["igst_amount"] = f"{max(0.0, igst):.2f}"
    result["grand_total"] = f"{max(0.0, grand_total):.2f}"

    return result


def main():
    pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDF files")
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
        output_file = "airindia_express_invoices_extracted.xlsx"
        df.to_excel(output_file, index=False)
        print(f"Written {len(results)} records to {output_file}")
        print(df.to_string())
    else:
        print("No data extracted.")


if __name__ == "__main__":
    main()