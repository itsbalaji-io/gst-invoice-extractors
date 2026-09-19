# Airline GST Invoice Extractors & Sorter

A comprehensive suite of Python scripts and automation utilities to classify, sort, and extract GST invoice details from airline invoice PDFs (Air India, Air India Express, IndiGo, etc.).

## 📦 Features & Structure

### 1. Master Batch Runner
- **`run_gst_extraction.bat`**: Windows one-click automated pipeline.
  - Automatically verifies Python installation (prompts permission to install via winget if missing).
  - Checks pip and required packages (`pdfplumber`, `openpyxl`, `pandas`), prompting permission to install if missing.
  - Provides an interactive execution menu: Full Pipeline (Default), Sort Only, Airline-Specific Excels Only, or Unified Summary.

### 2. Multi-Airline Unified Extractor
- **`extract_gst.py`**: Unified extraction pipeline with regex parsing for GSTIN, invoice numbers, dates, taxable values, CGST/SGST/IGST rates & amounts, grand totals, PNRs, and passenger names. Outputs results to structured **Excel (`.xlsx`)** and **JSON** files in `extracted_data/`.
- **`airline_patterns.py`**: Airline pattern library and classification engine supporting standard text matching and OCR fallbacks.

### 3. Airline Sorting & Organization
- **`sort_airline_invoices.py`**: Scans a directory of mixed PDF invoices, classifies each by airline, and automatically moves them into organized airline subdirectories (`Indigo/`, `Air_India_Express/`, `Air_India/`).

### 4. Airline-Specific Extractors
- **`indigo_gst_invoice_extractor.py`**: High-accuracy parser for IndiGo GST invoices and credit notes. Outputs to `indigo_invoices_extracted.xlsx`.
- **`airindia_express_gst_extractor.py`**: Specialized parser for Air India Express GST invoices. Outputs to `airindia_express_invoices_extracted.xlsx`.
- **`airindia_gst_extractor.py`**: Specialized parser for Air India (Ltd) GST invoices and debit notes. Outputs to `airindia_invoices_extracted.xlsx`.
- **`spicejet_gst_invoice_extractor.py`**: Specialized parser for SpiceJet GST invoices. Outputs to `spicejet_invoices_extracted.xlsx`.

## 🚀 Setup & Installation

### Option 1: Quick Start (Windows)
Double-click `run_gst_extraction.bat` or run:
```cmd
run_gst_extraction.bat
```
The batch runner will automatically check Python, ask permission to install any missing dependencies, and guide you through the process.

### Option 2: Command Line

1. **Install dependencies**:
```bash
pip install pdfplumber openpyxl pandas
```

2. **Sort raw invoices into airline folders**:
```bash
python sort_airline_invoices.py
```

3. **Run airline-specific extractors**:
```bash
python indigo_gst_invoice_extractor.py
python airindia_express_gst_extractor.py
python airindia_gst_extractor.py
python spicejet_gst_invoice_extractor.py
```

4. **Run unified multi-airline summary (outputs to `extracted_data/`)**:
```bash
python extract_gst.py
```
