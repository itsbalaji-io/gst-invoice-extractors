# Airline GST Invoice Extractors & Sorter

A comprehensive suite of Python scripts and automation utilities to classify, sort, and extract GST invoice details from airline invoice PDFs (Air India, Air India Express, IndiGo, SpiceJet, Vistara, Akasa Air, etc.).

## 📦 Features & Structure

### 1. Multi-Airline Unified Extractor & Batch Runner
- **`extract_gst.py`**: Unified extraction pipeline with regex parsing for GSTIN, invoice numbers, dates, taxable values, CGST/SGST/IGST rates & amounts, grand totals, PNRs, and passenger names. Outputs results to structured **Excel (`.xlsx`)** and **JSON** files.
- **`airline_patterns.py`**: Airline pattern library and classification engine supporting standard text matching and OCR fallbacks.
- **`run_gst_extraction.bat`**: Windows one-click batch runner that verifies Python, installs dependencies (`pdfplumber`, `openpyxl`), and executes the extraction pipeline.

### 2. Airline Sorting & Organization
- **`sort_airline_invoices.py`**: Scans a directory of mixed PDF invoices, classifies each by airline, and automatically moves them into organized airline subdirectories.

### 3. Airline-Specific Extractors & Tools
- **`airindia_express_gst_extractor.py`**: Specialized parser for Air India Express GST invoices.
- **`airindia_gst_extractor.py`**: Specialized parser for Air India GST invoices.
- **`indigo_gst_invoice_extractor.py`**: Specialized parser for IndiGo GST invoices.
- **`separate_indigo_invoices.py`**: Splits and organizes multi-invoice / combined IndiGo PDF documents.
- **`spicejet_gst_invoice_extractor.py`**: Specialized parser for SpiceJet GST invoices.

## 🚀 Setup & Installation

1. Clone this repository:
```bash
git clone https://github.com/itsbalaji-io/gst-invoice-extractors.git
cd gst-invoice-extractors
```

2. Install dependencies:
```bash
pip install pdfplumber openpyxl pandas
```
*(Optional for scanned PDFs OCR: `pip install marker-pdf`)*

## 🛠️ Usage

### Quick Start (Windows)
Double-click `run_gst_extraction.bat` or run:
```cmd
run_gst_extraction.bat
```

### Command Line
1. **Sort raw invoices into airline folders**:
```bash
python sort_airline_invoices.py
```

2. **Run unified GST extraction (outputs Excel & JSON to `extracted_data/`)**:
```bash
python extract_gst.py
# Or process flat folder:
python extract_gst.py --flat
```

3. **Run airline-specific extractors**:
```bash
python airindia_gst_extractor.py
python airindia_express_gst_extractor.py
python indigo_gst_invoice_extractor.py
python spicejet_gst_invoice_extractor.py
```
