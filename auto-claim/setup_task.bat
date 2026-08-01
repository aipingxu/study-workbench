@echo off
REM ============================================================
REM   WorkBuddy Daily Credits Auto-Claim Setup
REM   Windows Task Scheduler installer
REM ============================================================

setlocal enabledelayedexpansion

REM --- Python path (prefer WorkBuddy managed) ---
set "PYTHON=C:\Users\WeTrial\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PYTHON%" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found. Please install Python 3.x first.
        pause
        exit /b 1
    )
    for /f "tokens=*" %%i in ('where python') do set "PYTHON=%%i"
)

REM --- Script path ---
set "SCRIPT=%~dp0claim_credits.py"

echo ============================================================
echo   WorkBuddy Daily Credits Auto-Claim - Setup
echo ============================================================
echo.
echo Python: %PYTHON%
echo Script: %SCRIPT%
echo.

REM --- Step 1: Check playwright ---
echo [1/4] Checking Playwright...
"%PYTHON%" -c "import playwright" 2>nul
if errorlevel 1 (
    echo Installing playwright...
    "%PYTHON%" -m pip install playwright -q
    if errorlevel 1 (
        echo [ERROR] pip install failed. Check network.
        pause
        exit /b 1
    )
    "%PYTHON%" -m playwright install chromium
)
echo Playwright ready.
echo.

REM --- Step 2: Create Windows task ---
echo [2/4] Creating Windows scheduled task...
set "TASK_NAME=WorkBuddy_DailyCredits"
set "TASK_TIME=09:00"

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Build command line as a single string
set "CMD_LINE=\"%PYTHON%\" \"%SCRIPT%\""

schtasks /create /tn "%TASK_NAME%" /tr "%CMD_LINE%" /sc daily /st %TASK_TIME% /f
if errorlevel 1 (
    echo [ERROR] Failed to create scheduled task.
    echo Try running this script as Administrator.
    pause
    exit /b 1
)
echo Scheduled task created: daily at %TASK_TIME%
echo.

REM --- Step 3: First-time login ---
echo [3/4] First-time login setup
echo.
echo IMPORTANT: First run needs you to login to codebuddy.cn manually once.
echo A browser window will open. Please login.
echo After login, return here and press Enter.
echo.
pause >nul

call "%PYTHON%" "%SCRIPT%" --login
echo.

REM --- Step 4: Done ---
echo [4/4] Setup complete!
echo.
echo ============================================================
echo   All set!
echo ============================================================
echo.
echo - Daily at %TASK_TIME%, auto-claim 100 credits
echo - No need to open WorkBuddy, runs in background
echo - Log file: %~dp0claim_credits.log
echo - Re-login:  "%PYTHON%" "%SCRIPT%" --login
echo - Manual run: "%PYTHON%" "%SCRIPT%"
echo - Remove task: schtasks /delete /tn "%TASK_NAME%" /f
echo.
pause
endlocal