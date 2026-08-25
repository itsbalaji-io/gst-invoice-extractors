"""Airline classification patterns and logic."""

import re
from pathlib import Path
from typing import Literal

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

# Additional patterns found in scanned/unclassified PDFs
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


def classify_pdf(pdf_path: Path) -> AirlineName:
    """Return airline name or 'Unknown'/'Error'."""
    # Try text extraction first (fast)
    text = extract_text_pdfplumber(pdf_path)

    if text and len(text.strip()) > 50:
        # Has extractable text - use normal patterns
        for airline, patterns in AIRLINE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return airline  # type: ignore[return-value]
        return "Unknown"

    # No/low text - try OCR with marker (slow but accurate)
    text = extract_text_marker_ocr(pdf_path)
    if text and len(text.strip()) > 50:
        # Use scanned-specific patterns (more flexible for OCR errors)
        for airline, patterns in SCANNED_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return airline  # type: ignore[return-value]
        # Fallback to normal patterns
        for airline, patterns in AIRLINE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return airline  # type: ignore[return-value]
        return "Unknown"

    return "Error"


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Fast text extraction using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        return ""

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


def get_source_dir() -> Path:
    """Get the source PDF directory - searches common locations."""
    base = Path(__file__).parent
    # Check common locations relative to script
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
    # Fallback: return first candidate (will show error in main)
    return candidates[0]