#!/usr/bin/env python3
"""
Separate Indigo GST invoices from other airline GST invoices.
Scans PDF files in a given directory, moves those identified as Indigo GST invoices
to a subdirectory named 'Indigo_Invoices'.
"""

import os
import re
import shutil
from pathlib import Path

import pdfplumber


def is_indigo_invoice(pdf_path: str) -> bool:
    """
    Return True if the PDF appears to be an Indigo GST invoice.
    Detection based on presence of Indigo-specific keywords in the first page text.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from first page only (usually enough)
            first_page = pdf.pages[0] if pdf.pages else None
            if not first_page:
                return False
            text = first_page.extract_text() or ""
            # Normalize whitespace
            text = " ".join(text.split())
            # Case-insensitive patterns
            patterns = [
                r"IndiGo",
                r"goindigo\.in",
                r"Interglobe Aviation Limited",
                r"AABCI2726B",  # part of Indigo GSTIN
            ]
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return True
            return False
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return False


def main(source_dir: str = None):
    if source_dir is None:
        # Default to script's directory
        source_dir = os.path.dirname(os.path.abspath(__file__))
    source_path = Path(source_dir)
    if not source_path.is_dir():
        print(f"Error: {source_dir} is not a valid directory.")
        return

    dest_dir = source_path / "Indigo_Invoices"
    dest_dir.mkdir(exist_ok=True)

    pdf_files = list(source_path.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in", source_dir)
        return

    moved = 0
    for pdf_file in pdf_files:
        if is_indigo_invoice(str(pdf_file)):
            dest_path = dest_dir / pdf_file.name
            # Avoid overwriting existing file
            counter = 1
            while dest_path.exists():
                stem = pdf_file.stem
                suffix = pdf_file.suffix
                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            shutil.move(str(pdf_file), str(dest_path))
            print(f"Moved: {pdf_file.name} -> {dest_dir.name}/{dest_path.name}")
            moved += 1
        else:
            print(f"Not Indigo (leave): {pdf_file.name}")

    print(f"\nDone. Moved {moved} invoice(s) to {dest_dir}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Allow optional directory argument
        target_dir = sys.argv[1]
    else:
        target_dir = None
    main(target_dir)