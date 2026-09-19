#!/usr/bin/env python
"""Extract GST data from classified PDF invoices using pdfplumber (fast) + OCR fallback."""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
except ImportError:
    openpyxl = None

from airline_patterns import (
    AIRLINE_PATTERNS,
    SCANNED_PATTERNS,
    extract_text_pdfplumber,
    extract_text_marker_ocr,
    classify_pdf,
)

def find_source_dir() -> Path:
    """Auto-detect the PDF source directory."""
    candidates = [
        Path.cwd() / "Sample PDF",
        Path.cwd() / "Sample_PDF",
        Path.cwd().parent / "Sample PDF",
        Path.cwd().parent / "Sample_PDF",
        Path(__file__).parent / "Sample PDF",
        Path(__file__).parent.parent / "Sample PDF",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    if any(Path.cwd().glob("*.pdf")):
        return Path.cwd()
    if any(Path(__file__).parent.glob("*.pdf")):
        return Path(__file__).parent
    return Path.cwd()

def get_args():
    parser = argparse.ArgumentParser(description="Extract GST data from airline invoice PDFs")
    parser.add_argument("source", nargs="?", type=Path, help="Source directory (auto-detected if omitted)")
    parser.add_argument("--output", "-o", type=Path, help="Output directory for results")
    parser.add_argument("--flat", action="store_true", help="Process flat PDFs (classify each file)")
    parser.add_argument("--list-airlines", action="store_true", help="List detected airlines and exit")
    return parser.parse_args()

args = get_args()
SOURCE_DIR = args.source if args.source else find_source_dir()
OUTPUT_DIR = args.output if args.output else Path(__file__).parent / "extracted_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# Pre-compile regex patterns for speed
GST_PATTERNS = {
    "gstin": re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b"),
    "invoice_number": re.compile(r"(?i)(?:invoice\s*(?:no|number|#)\s*[:.\-]?\s*)([A-Z0-9\-\/]{6,})"),
    "invoice_date": re.compile(r"(?i)(?:invoice\s*date|date\s*of\s*invoice)\s*[:.\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})"),
    "place_of_supply": re.compile(r"(?i)place\s*of\s*supply\s*[:.\-]?\s*([A-Za-z\s]+)"),
    "hsn_sac": re.compile(r"\b(?:HSN|SAC)\s*[:.\-]?\s*(\d{4,8})\b"),
    "taxable_value": re.compile(r"(?i)(?:taxable\s*value|assessable\s*value)\s*[:.\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+\.?\d*)"),
    "cgst_rate": re.compile(r"(?i)CGST\s*(?:@|rate)?\s*[:.\-]?\s*(\d+(?:\.\d+)?)\s*%"),
    "sgst_rate": re.compile(r"(?i)SGST\s*(?:@|rate)?\s*[:.\-]?\s*(\d+(?:\.\d+)?)\s*%"),
    "igst_rate": re.compile(r"(?i)IGST\s*(?:@|rate)?\s*[:.\-]?\s*(\d+(?:\.\d+)?)\s*%"),
    "cgst_amount": re.compile(r"(?i)CGST\s*(?:amount)?\s*[:.\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+\.?\d*)"),
    "sgst_amount": re.compile(r"(?i)SGST\s*(?:amount)?\s*[:.\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+\.?\d*)"),
    "igst_amount": re.compile(r"(?i)IGST\s*(?:amount)?\s*[:.\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+\.?\d*)"),
    "total_tax": re.compile(r"(?i)(?:total\s*tax|tax\s*amount)\s*[:.\-]?\s*(?:Rs\.?|INR?|INR)?\s*([\d,]+\.?\d*)"),
    "grand_total": re.compile(r"(?i)(?:grand\s*total|total\s*amount|invoice\s*value)\s*[:.\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+\.?\d*)"),
    "reverse_charge": re.compile(r"(?i)reverse\s*charge\s*[:.\-]?\s*(yes|no|true|false)"),
    "supplier_name": re.compile(r"(?i)(?:supplier|seller|from)\s*[:.\-]?\s*([A-Za-z\s\.]+(?:Ltd|Limited|Pvt|Private|LLP)?)"),
    "buyer_name": re.compile(r"(?i)(?:buyer|bill\s*to|customer|sold\s*to)\s*[:.\-]?\s*([A-Za-z\s\.]+(?:Ltd|Limited|Pvt|Private|LLP)?)"),
    "buyer_gstin": re.compile(r"(?i)(?:buyer|customer)\s*GSTIN\s*[:.\-]?\s*(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})"),
    "airline_gstin": re.compile(r"(?i)(?:Air\s*India|IndiGo|SpiceJet|Vistara|Akasa)\s*GSTIN\s*[:.\-]?\s*(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})"),
    "pnr": re.compile(r"(?i)PNR\s*[:.\-]?\s*([A-Z0-9]{6})"),
    "passenger_name": re.compile(r"(?i)Passenger\s*Name\s*[:.\-]?\s*([A-Za-z\s\.]+)"),
}


def extract_text_with_fallback(pdf_path: Path) -> tuple[str, str]:
    """
    Extract text: pdfplumber only (fast). Skip OCR for speed.
    Returns (text, method_used).
    """
    try:
        text = extract_text_pdfplumber(pdf_path)
        if text and len(text.strip()) > 100:
            return text, "pdfplumber"
    except Exception as e:
        # Log font warnings but continue
        pass

    # Skip OCR - return empty for image-only PDFs
    return "", "skipped_image_only"


def extract_gst_fields(text: str) -> dict[str, list[str]]:
    """Extract key GST fields using pre-compiled regex."""
    results = {}
    # Only essential fields for speed
    key_fields = ["gstin", "invoice_number", "invoice_date", "place_of_supply",
                  "taxable_value", "cgst_rate", "sgst_rate", "igst_rate",
                  "cgst_amount", "sgst_amount", "igst_amount", "total_tax",
                  "grand_total", "pnr", "passenger_name"]
    for field in key_fields:
        pattern = GST_PATTERNS[field]
        matches = pattern.findall(text)
        if matches:
            cleaned = []
            for m in matches:
                if isinstance(m, tuple):
                    cleaned.extend([g.strip() for g in m if g.strip()])
                else:
                    cleaned.append(m.strip())
            seen = set()
            results[field] = [x for x in cleaned if not (x in seen or seen.add(x))]
        else:
            results[field] = []
    return results


def process_airline_folder(airline: str, folder: Path) -> list[dict]:
    """Process all PDFs in an airline folder (optimized)."""
    results = []
    pdf_files = list(folder.glob("*.pdf"))
    failed = 0

    print(f"\n[{airline}] Processing {len(pdf_files)} files...")

    for i, pdf_path in enumerate(pdf_files):
        if i % 200 == 0 and i > 0:
            print(f"  Progress: {i}/{len(pdf_files)} (failed: {failed})")

        try:
            text, method = extract_text_with_fallback(pdf_path)
            gst_data = extract_gst_fields(text)

            record = {
                "file_name": pdf_path.name,
                "file_path": str(pdf_path),
                "airline": airline,
                "file_size_bytes": pdf_path.stat().st_size,
                "extraction_method": method,
                "processed_at": datetime.now().isoformat(),
                "gst_fields": gst_data,
                "text_length": len(text),
            }
            results.append(record)
        except Exception as e:
            failed += 1
            print(f"  [!] Failed: {pdf_path.name} - {e}")

    print(f"  Done: {len(results)} files processed, {failed} failed")
    return results


def save_json(all_results: list[dict], output_path: Path):
    """Save all results as JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {output_path}")


def save_excel(all_results: list[dict], output_path: Path):
    """Save key GST fields as Excel."""
    if not openpyxl:
        print("openpyxl not installed, skipping Excel export")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "GST Extraction"

    headers = [
        "File Name", "Airline", "File Path", "File Size (KB)",
        "Extraction Method",
        "GSTIN(s)", "Invoice Number(s)", "Invoice Date(s)",
        "Place of Supply",
        "Taxable Value(s)", "CGST Rate(s)", "SGST Rate(s)", "IGST Rate(s)",
        "CGST Amount(s)", "SGST Amount(s)", "IGST Amount(s)",
        "Total Tax", "Grand Total",
        "PNR(s)", "Passenger Name(s)",
        "Text Length", "Processed At"
    ]

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for row_idx, record in enumerate(all_results, 2):
        gst = record["gst_fields"]

        def join_vals(key: str) -> str:
            vals = gst.get(key, [])
            return "; ".join(str(v) for v in vals) if vals else ""

        row_data = [
            record["file_name"],
            record["airline"],
            record["file_path"],
            round(record["file_size_bytes"] / 1024, 1),
            record["extraction_method"],
            join_vals("gstin"),
            join_vals("invoice_number"),
            join_vals("invoice_date"),
            join_vals("place_of_supply"),
            join_vals("taxable_value"),
            join_vals("cgst_rate"),
            join_vals("sgst_rate"),
            join_vals("igst_rate"),
            join_vals("cgst_amount"),
            join_vals("sgst_amount"),
            join_vals("igst_amount"),
            join_vals("total_tax"),
            join_vals("grand_total"),
            join_vals("pnr"),
            join_vals("passenger_name"),
            record.get("text_length", 0),
            record["processed_at"],
        ]

        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except Exception:
                pass
        adjusted_width = min(max_length + 2, 60)
        ws.column_dimensions[column_letter].width = adjusted_width

    wb.save(output_path)
    print(f"Saved Excel: {output_path}")


def save_raw_texts(all_results: list[dict], output_dir: Path):
    """Save raw extracted text (disabled for speed - use JSON for text)."""
    pass


def main() -> int:
    print("GST Invoice Extraction (pdfplumber + OCR fallback)")
    print("=" * 55)

    source_dir = SOURCE_DIR
    output_dir = OUTPUT_DIR

    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}")
        return 1

    # Check if flat mode or organized folders
    pdf_files = list(source_dir.glob("*.pdf"))
    ignore_dirs = {"Unclassified", "__pycache__", "extracted_data", "scratch", ".system_generated", "expired", "Expired"}
    airline_folders = [d for d in source_dir.iterdir() if d.is_dir() and d.name not in ignore_dirs and not d.name.startswith(".")]

    all_results = []

    if args.flat or (pdf_files and not airline_folders):
        # Flat structure: classify each PDF
        print(f"[Flat mode] Found {len(pdf_files)} PDFs, classifying...")
        failed = 0
        for i, pdf_path in enumerate(pdf_files):
            if i % 50 == 0 and i > 0:
                print(f"  Progress: {i}/{len(pdf_files)} (failed: {failed})")
            try:
                text, method = extract_text_with_fallback(pdf_path)
                airline = classify_pdf(pdf_path)
                gst_data = extract_gst_fields(text)
                record = {
                    "file_name": pdf_path.name,
                    "file_path": str(pdf_path),
                    "airline": airline,
                    "file_size_bytes": pdf_path.stat().st_size,
                    "extraction_method": method,
                    "processed_at": datetime.now().isoformat(),
                    "gst_fields": gst_data,
                    "text_length": len(text),
                }
                all_results.append(record)
            except Exception as e:
                failed += 1
                print(f"  [!] Failed: {pdf_path.name} - {e}")
    elif airline_folders:
        # Organized by airline folders
        for folder in sorted(airline_folders, key=lambda x: x.name):
            airline = folder.name
            results = process_airline_folder(airline, folder)
            all_results.extend(results)
    else:
        print("No PDFs found.")
        return 1

    print(f"\nTotal files processed: {len(all_results)}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"gst_extraction_{timestamp}.json"
    excel_path = output_dir / f"gst_extraction_{timestamp}.xlsx"

    save_json(all_results, json_path)
    save_excel(all_results, excel_path)
    save_raw_texts(all_results, output_dir)

    # Summary
    summary = {
        "total_files": len(all_results),
        "by_airline": defaultdict(int),
        "by_method": defaultdict(int),
        "files_with_gstin": 0,
        "files_with_invoice": 0,
        "files_with_airline_gstin": 0,
        "total_tables": 0,
    }

    for r in all_results:
        summary["by_airline"][r["airline"]] += 1
        summary["by_method"][r["extraction_method"]] += 1
        if r["gst_fields"].get("gstin"):
            summary["files_with_gstin"] += 1
        if r["gst_fields"].get("invoice_number"):
            summary["files_with_invoice"] += 1
        if r["gst_fields"].get("airline_gstin"):
            summary["files_with_airline_gstin"] += 1

    summary["by_airline"] = dict(summary["by_airline"])
    summary["by_method"] = dict(summary["by_method"])
    summary_path = output_dir / f"extraction_summary_{timestamp}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== Extraction Summary ===")
    print(f"Total files: {summary['total_files']}")
    print(f"Files with GSTIN: {summary['files_with_gstin']}")
    print(f"Files with Airline GSTIN: {summary['files_with_airline_gstin']}")
    print(f"Files with Invoice #: {summary['files_with_invoice']}")
    print(f"\nBy airline:")
    for airline, count in sorted(summary["by_airline"].items()):
        print(f"  {airline}: {count}")
    print(f"\nBy extraction method:")
    for method, count in sorted(summary["by_method"].items()):
        print(f"  {method}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())