@echo off
REM ============================================================
REM GST Invoice Extraction Runner
REM Checks Python, installs dependencies, runs extraction
REM ============================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ============================================================
echo GST Invoice Extraction - System Check & Run
echo ============================================================
echo.

REM ---- Check Python ----
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)
for /f "tokens=2" %%a in ('python --version 2^>^&1') do set PY_VER=%%a
echo Found Python %PY_VER%

REM Check Python version >= 3.8
for /f "tokens=2 delims=." %%a in ("%PY_VER%") do set PY_MINOR=%%b
if %PY_MINOR% lss 8 (
    echo WARNING: Python 3.8+ recommended (found 3.%PY_MINOR%)
)

echo.

REM ---- Check pip ----
echo [2/4] Checking pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pip not available
    echo Try: python -m ensurepip --upgrade
    pause
    exit /b 1
)
echo pip OK

echo.

REM ---- Check/Install Dependencies ----
echo [3/4] Checking required packages...
set MISSING=0

python -c "import pdfplumber" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing pdfplumber...
    python -m pip install pdfplumber --quiet
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install pdfplumber
        set MISSING=1
    )
) else (
    echo pdfplumber: OK
)

python -c "import openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing openpyxl...
    python -m pip install openpyxl --quiet
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install openpyxl
        set MISSING=1
    )
) else (
    echo openpyxl: OK
)

REM Optional: marker-pdf for OCR (slow, large)
python -c "import marker" >nul 2>&1
if %errorlevel% neq 0 (
    echo marker-pdf (OCR): Not installed (optional - for scanned PDFs only)
    echo To install: python -m pip install marker-pdf
) else (
    echo marker-pdf (OCR): OK
)

if %MISSING% equ 1 (
    echo.
    echo Some required packages failed to install.
    echo Try running manually: python -m pip install pdfplumber openpyxl
    pause
    exit /b 1
)

echo.

REM ---- Run Extraction ----
echo [4/4] Running GST extraction...
echo.

REM Check if script exists
if not exist "%SCRIPT_DIR%extract_gst.py" (
    echo ERROR: extract_gst.py not found in %SCRIPT_DIR%
    pause
    exit /b 1
)

if not exist "%SCRIPT_DIR%airline_patterns.py" (
    echo ERROR: airline_patterns.py not found in %SCRIPT_DIR%
    pause
    exit /b 1
)

echo Starting extraction with --flat mode...
echo Source: %SCRIPT_DIR%
echo.

python "%SCRIPT_DIR%extract_gst.py" --flat

echo.
echo ============================================================
echo Extraction complete!
echo Output saved to: %SCRIPT_DIR%extracted_data\
echo ============================================================
pause
