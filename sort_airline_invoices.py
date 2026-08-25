#!/usr/bin/env python3
"""
Sort airline GST invoices into airline-specific subdirectories.
Scans PDF files in a given directory, classifies each by airline,
and moves them into subdirectories named after each airline.
"""

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Literal

import pdfplumber


AIRLINE_PATTERNS: dict[str, list[str]] = {
    "Air India Express": [
        r"\bAir India Express\b",
        r"\bAIX Connect\b",
        r"\bAir India Express.*GSTIN\b",
    ],
    "Air India": [
        r"\bAIR INDIA LTD\b",
        r"\bAir India Ltd\b",
        r"\b27AACCN6194P1ZP\b",
    ],
    "Indigo": [
        r"\bIndiGo\b",
        r"\bInterglobe Aviation\b",
        r"\bgoindigo\.in\b",
        r"\bAABCI2726B\b",
    ],
    "SpiceJet": [
        r"\bSpiceJet\b",
        r"\bSpice Jet\b",
        r"\bGSTIN of SpiceJet\b",
    ],
    "Vistara": [
        r"\bVistara\b",
        r"\bTata SIA Airlines\b",
    ],
    "Akasa Air": [
        r"\bAkasa Air\b",
        r"\bSNV Aviation\b",
    ],
    "Roundtrip Ledger": [
        r"\bRoundtrip\.in LLP\b",
        r"\bLedger Account\b",
    ],
}

SCANNED_PATTERNS: dict[str, list[str]] = {
    "Air India": [
        r"\bAIR\s*INDIA\b",
        r"\bAir\s*India\s*Ltd\b",
        r"33AACCN6194P2ZV",
    ],
    "Indigo": [
        r"\bIndiGo\b",
        r"\bInter\s*Globe\s*Aviation\b",
        r"goindigo",
        r"AABCI2726B",
    ],
    "SpiceJet": [
        r"\bSpice\s*Jet\b",
        r"SpiceJet",
    ],
    "Vistara": [
        r"\bVistara\b",
        r"Tata\s*SIA",
    ],
    "Akasa Air": [
        r"Akasa\s*Air",
        r"SNV\s*Aviation",
    ],
    "Roundtrip Ledger": [
        r"Round\s*trip",
        r"Ledger\s*Account",
    ],
}

AirlineName = Literal[
    "Air India Express",
    "Air India",
    "Indigo",
    "SpiceJet",
    "Vistara",
    "Akasa Air",
    "Roundtrip Ledger",
    "Unknown",
    "Error",
]


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Fast text extraction using pdfplumber."""
    try:
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception:
        return ""


def extract_text_marker_ocr(pdf_path: Path) -> str:
    """OCR extraction using marker (for scanned PDFs)."""
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
    except ImportError:
        return ""

    try:
        model_dict = create_model_dict()
        converter = PdfConverter(artifact_dict=model_dict)
        rendered = converter(str(pdf_path))
        text, _ = text_from_rendered(rendered)
        return text
    except Exception:
        return ""


def classify_pdf(pdf_path: Path) -> AirlineName:
    """Return airline name or 'Unknown'/'Error'."""
    text = extract_text_pdfplumber(pdf_path)

    if text and len(text.strip()) > 50:
        for airline, patterns in AIRLINE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return airline  # type: ignore[return-value]
        return "Unknown"

    text = extract_text_marker_ocr(pdf_path)
    if text and len(text.strip()) > 50:
        for airline, patterns in SCANNED_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return airline  # type: ignore[return-value]
        for airline, patterns in AIRLINE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return airline  # type: ignore[return-value]
        return "Unknown"

    return "Error"


def get_source_dir() -> Path:
    """Get the source PDF directory - searches common locations."""
    base = Path(__file__).parent
    candidates = [
        base / "Sample PDF",
        base.parent / "Sample PDF",
        base / "Gst invoice",
        base / "Gstinvoice",
        base / "pdfs",
        base / "invoices",
        base / "PDF",
        Path.cwd() / "Sample PDF",
        Path.cwd() / "Gst invoice",
        Path.cwd() / "Gstinvoice",
        Path.cwd() / "pdfs",
        Path.cwd() / "invoices",
        Path.cwd() / "PDF",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return candidates[0]


def main(source_dir: str | None = None):
    if source_dir is None:
        source_dir = str(get_source_dir())
    source_path = Path(source_dir)
    if not source_path.is_dir():
        print(f"Error: {source_dir} is not a valid directory.")
        return

    pdf_files = list(source_path.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in", source_dir)
        return

    counts: dict[str, int] = {}
    for pdf_file in pdf_files:
        airline = classify_pdf(pdf_file)

        if airline in ("Unknown", "Error"):
            dest_dir = source_path / airline
            print(f"{airline}: {pdf_file.name}")
        else:
            dest_dir = source_path / airline.replace(" ", "_")
            dest_dir.mkdir(exist_ok=True)

        dest_dir.mkdir(exist_ok=True)
        dest_path = dest_dir / pdf_file.name

        counter = 1
        while dest_path.exists():
            stem = pdf_file.stem
            suffix = pdf_file.suffix
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.move(str(pdf_file), str(dest_path))
        print(f"Moved: {pdf_file.name} -> {dest_dir.name}/{dest_path.name}")
        counts[airline] = counts.get(airline, 0) + 1

    print("\nSummary:")
    for airline, count in sorted(counts.items()):
        print(f"  {airline}: {count}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = None
    main(target_dir)