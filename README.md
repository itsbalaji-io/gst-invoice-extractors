# Airline GST Invoice Extractors & Sorter

A collection of Python scripts to classify, sort, and extract GST invoice details from airline invoice PDFs (Air India, Air India Express, IndiGo, SpiceJet, etc.).

## 📦 Features

- **Automatic Sorting (`sort_airline_invoices.py`)**: Classifies mixed PDF invoices by airline and organizes them into categorized folders.
- **Air India Express Extractor (`airindia_express_gst_extractor.py`)**: Extracts structured GST data from Air India Express invoices.
- **Air India Extractor (`airindia_gst_extractor.py`)**: Extracts GST invoice details from Air India PDFs.
- **IndiGo Extractor & Separator (`indigo_gst_invoice_extractor.py`, `separate_indigo_invoices.py`)**: Extracts GST fields and separates combined IndiGo invoice files.
- **SpiceJet Extractor (`spicejet_gst_invoice_extractor.py`)**: Extracts structured GST invoice details from SpiceJet PDFs.

## 🚀 Setup & Installation

1. Clone this repository:
```bash
git clone https://github.com/itsbalaji-io/gst-invoice-extractors.git
cd gst-invoice-extractors
```

2. Install dependencies:
```bash
pip install pdfplumber pandas openpyxl
```

## 🛠️ Usage

### 1. Sort Airline Invoices
Organize raw PDFs into airline-specific subdirectories:
```bash
python sort_airline_invoices.py
```

### 2. Extract GST Data
Run the relevant extractor script for your airline invoices:
```bash
python airindia_gst_extractor.py
python airindia_express_gst_extractor.py
python indigo_gst_invoice_extractor.py
python spicejet_gst_invoice_extractor.py
```
