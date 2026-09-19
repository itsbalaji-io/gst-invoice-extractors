@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM Airline GST Invoice Extraction and Sorter Pipeline
REM Checks Python and dependencies, prompts for installation if missing,
REM sorts PDFs airline-wise, and extracts details to Excel.
REM ============================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
title Airline GST Invoice Extractor

echo ============================================================
echo      Airline GST Invoice Extraction and Sorter Pipeline
echo ============================================================
echo.

REM ------------------------------------------------------------
REM [1/4] Check Python Installation
REM ------------------------------------------------------------
echo [Step 1/4] Checking Python installation...
set "PY_CMD=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    ) else (
        goto PYTHON_MISSING
    )
)
goto PYTHON_OK

:PYTHON_MISSING
echo.
echo [!] ERROR: Python is not detected in your system PATH.
echo.
set "INSTALL_PY=Y"
set /p "INSTALL_PY=Would you like to install Python 3.12 automatically via winget? (Y/N) [Default: Y]: "
set "INSTALL_PY=%INSTALL_PY: =%"

if /i "%INSTALL_PY%"=="Y" goto DO_INSTALL_PY
if /i "%INSTALL_PY%"=="YES" goto DO_INSTALL_PY
if /i "%INSTALL_PY%"=="" goto DO_INSTALL_PY

echo.
echo Python is required to run the extraction tools. Exiting.
pause
exit /b 1

:DO_INSTALL_PY
echo.
echo Installing Python 3.12 via winget...
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
if %errorlevel% neq 0 goto PY_WINGET_FAILED

echo [OK] Python installed successfully. Please restart this batch file.
pause
exit /b 0

:PY_WINGET_FAILED
echo.
echo [!] Automated installation failed or winget is not available.
echo Opening official Python download page in your browser...
start https://www.python.org/downloads/
echo Note: Please make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:PYTHON_OK
for /f "tokens=2" %%a in ('%PY_CMD% --version 2^>^&1') do set "PY_VER=%%a"
echo [OK] Python %PY_VER% is available (Command: %PY_CMD%)
echo.

REM ------------------------------------------------------------
REM [2/4] Check pip Package Manager
REM ------------------------------------------------------------
echo [Step 2/4] Checking pip package manager...
%PY_CMD% -m pip --version >nul 2>&1
if %errorlevel% equ 0 goto PIP_OK

echo.
echo [!] WARNING: pip was not detected.
set "INSTALL_PIP=Y"
set /p "INSTALL_PIP=Would you like to install/repair pip now? (Y/N) [Default: Y]: "
set "INSTALL_PIP=%INSTALL_PIP: =%"

if /i "%INSTALL_PIP%"=="Y" goto DO_INSTALL_PIP
if /i "%INSTALL_PIP%"=="YES" goto DO_INSTALL_PIP
if /i "%INSTALL_PIP%"=="" goto DO_INSTALL_PIP

echo.
echo Cannot install required packages without pip. Exiting.
pause
exit /b 1

:DO_INSTALL_PIP
echo.
echo Configuring pip via ensurepip...
%PY_CMD% -m ensurepip --upgrade
if %errorlevel% neq 0 (
    echo [!] Failed to configure pip. Exiting.
    pause
    exit /b 1
)

:PIP_OK
echo [OK] pip is available.
echo.

REM ------------------------------------------------------------
REM [3/4] Check and Prompt for Required Python Libraries
REM ------------------------------------------------------------
echo [Step 3/4] Checking required dependencies...
%PY_CMD% -c "import fitz, pdfplumber, openpyxl, pandas" >nul 2>&1
if %errorlevel% equ 0 goto DEPS_OK

echo.
echo [!] One or more required packages are missing:
%PY_CMD% -c "import importlib.util as u; [print(('    [OK]      ' if u.find_spec(p) else '    [MISSING] ') + p) for p in ['fitz', 'pdfplumber', 'openpyxl', 'pandas']]"
echo.
set "INSTALL_DEPS=Y"
set /p "INSTALL_DEPS=Do you give permission to install the missing packages now? (Y/N) [Default: Y]: "
set "INSTALL_DEPS=%INSTALL_DEPS: =%"

if /i "%INSTALL_DEPS%"=="Y" goto DO_INSTALL_DEPS
if /i "%INSTALL_DEPS%"=="YES" goto DO_INSTALL_DEPS
if /i "%INSTALL_DEPS%"=="" goto DO_INSTALL_DEPS

echo.
echo [!] Installation cancelled. The script cannot extract invoice data without dependencies.
echo Press any key to exit...
pause >nul
exit /b 1

:DO_INSTALL_DEPS
echo.
echo ============================================================
echo Installing missing libraries via pip...
echo ============================================================
%PY_CMD% -m pip install pymupdf pdfplumber openpyxl pandas
if %errorlevel% neq 0 goto INSTALL_FAILED

echo.
echo [OK] All dependencies installed successfully!
goto DEPS_OK

:INSTALL_FAILED
echo.
echo [!] ERROR: Failed to install some dependencies.
echo Please check your internet connection or run manually:
echo   %PY_CMD% -m pip install pymupdf pdfplumber openpyxl pandas
echo.
echo Press any key to exit...
pause >nul
exit /b 1

:DEPS_OK
echo [OK] All required packages are installed and ready.
echo.

REM ------------------------------------------------------------
REM [4/4] Pipeline Execution Menu
REM ------------------------------------------------------------
echo ============================================================
echo Select Pipeline Action:
echo ============================================================
echo  [1] Full Pipeline: Sort PDFs + All Airline Excels + Unified Summary (Default)
echo  [2] Sort Invoices Only (Moves PDFs into airline folders)
echo  [3] Extract Airline-Specific Excels Only (Indigo, AI Express, Air India)
echo  [4] Unified Multi-Airline Extraction Only (extracted_data/)
echo ============================================================
set "USER_CHOICE=1"
set /p "USER_CHOICE=Enter choice (1-4) [Press ENTER for 1]: "
set "USER_CHOICE=%USER_CHOICE: =%"

if "%USER_CHOICE%"=="2" goto DO_SORT
if "%USER_CHOICE%"=="3" goto DO_AIRLINES
if "%USER_CHOICE%"=="4" goto DO_UNIFIED

:DO_FULL
echo.
echo ------------------------------------------------------------
echo [Action 1/3] Sorting invoices into airline folders...
echo ------------------------------------------------------------
%PY_CMD% "%SCRIPT_DIR%sort_airline_invoices.py"

:DO_AIRLINES
echo.
echo ------------------------------------------------------------
echo [Action 2/3] Extracting Airline-Specific Excel Reports...
echo ------------------------------------------------------------

if exist "%SCRIPT_DIR%Indigo" (
    echo.
    echo --- Processing IndiGo Invoices ---
    %PY_CMD% "%SCRIPT_DIR%indigo_gst_invoice_extractor.py"
) else (
    echo Notice: Indigo folder not found, skipping.
)

if exist "%SCRIPT_DIR%Air_India_Express" (
    echo.
    echo --- Processing Air India Express Invoices ---
    %PY_CMD% "%SCRIPT_DIR%airindia_express_gst_extractor.py"
) else (
    echo Notice: Air_India_Express folder not found, skipping.
)

if exist "%SCRIPT_DIR%Air_India" (
    echo.
    echo --- Processing Air India Invoices ---
    %PY_CMD% "%SCRIPT_DIR%airindia_gst_extractor.py"
) else (
    echo Notice: Air_India folder not found, skipping.
)

if exist "%SCRIPT_DIR%SpiceJet" (
    echo.
    echo --- Processing SpiceJet Invoices ---
    %PY_CMD% "%SCRIPT_DIR%spicejet_gst_invoice_extractor.py"
)

if "%USER_CHOICE%"=="3" goto FINISHED

:DO_UNIFIED
echo.
echo ------------------------------------------------------------
echo [Action 3/3] Generating Unified Multi-Airline Report...
echo ------------------------------------------------------------
%PY_CMD% "%SCRIPT_DIR%extract_gst.py"
if "%USER_CHOICE%"=="4" goto FINISHED

goto FINISHED

:DO_SORT
echo.
echo ------------------------------------------------------------
echo Sorting invoices into airline folders...
echo ------------------------------------------------------------
%PY_CMD% "%SCRIPT_DIR%sort_airline_invoices.py"
goto FINISHED

:FINISHED
echo.
echo ============================================================
echo                     EXECUTION COMPLETE
echo ============================================================
echo Output Excel Files Generated:
if exist "%SCRIPT_DIR%indigo_invoices_extracted.xlsx" (
    echo   [+] indigo_invoices_extracted.xlsx
)
if exist "%SCRIPT_DIR%airindia_express_invoices_extracted.xlsx" (
    echo   [+] airindia_express_invoices_extracted.xlsx
)
if exist "%SCRIPT_DIR%airindia_invoices_extracted.xlsx" (
    echo   [+] airindia_invoices_extracted.xlsx
)
if exist "%SCRIPT_DIR%spicejet_invoices_extracted.xlsx" (
    echo   [+] spicejet_invoices_extracted.xlsx
)
if exist "%SCRIPT_DIR%extracted_data" (
    echo   [+] extracted_data\ - Consolidated Excel and JSON reports
)
echo ============================================================
echo.
pause
