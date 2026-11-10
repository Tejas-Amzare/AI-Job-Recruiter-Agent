@echo off
REM ============================================================
REM  AI Recruiter - one-click runner
REM  Double-click this file to search jobs and open the report.
REM ============================================================
setlocal
cd /d "%~dp0"

title AI Recruiter - Job Discovery

echo ============================================================
echo   AI RECRUITER - Automatic Job Discovery ^& Resume Matching
echo ============================================================
echo.

REM --- Pick a Python launcher (prefer the 'py' launcher) ---
set "PY=py"
where py >nul 2>nul || set "PY=python"

REM --- Ensure dependencies are installed (quiet, only if needed) ---
echo [1/3] Checking dependencies...
%PY% -c "import requests, bs4, pandas, openpyxl, dateutil, yaml" >nul 2>nul
if errorlevel 1 (
    echo     Installing required packages, please wait...
    %PY% -m pip install -r requirements.txt
) else (
    echo     All dependencies present.
)
echo.

REM --- Freshness window in hours (default 72). Change if you like. ---
set "WINDOW=72"

echo [2/3] Searching job sources ^(last %WINDOW% hours^)...
echo       This can take a few minutes. Please wait...
echo.
%PY% -m ai_recruiter.main --window %WINDOW%
set "RC=%ERRORLEVEL%"
echo.

if not "%RC%"=="0" (
    echo [!] The run reported an error ^(code %RC%^). See logs\ai_recruiter.log
    echo.
    pause
    exit /b %RC%
)

echo [3/3] Opening the Excel report...
if exist "reports\AI_Job_Research_Report.xlsx" (
    start "" "reports\AI_Job_Research_Report.xlsx"
) else (
    echo     Report not found - check the console output above.
)

echo.
echo Done. You can close this window.
pause
endlocal

