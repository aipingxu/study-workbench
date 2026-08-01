@echo off
REM ============================================================
REM   WorkBuddy Daily Credits Auto-Claim Setup
REM   Windows Task Scheduler installer (12:00 + login trigger)
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

REM --- Step 2: Create Windows task (12:00 daily + login trigger) ---
echo [2/4] Creating Windows scheduled task...
echo   - Trigger 1: Daily at 12:00
echo   - Trigger 2: On user login (missed-day catch-up)
echo.

powershell -NoProfile -Command ^
  "$python='%PYTHON%'; $script='%SCRIPT%';" ^
  "$action=New-ScheduledTaskAction -Execute $python -Argument ('\"'+$script+'\"');" ^
  "$t1=New-ScheduledTaskTrigger -Daily -At '12:00';" ^
  "$t2=New-ScheduledTaskTrigger -AtLogOn -User 'WeTrial';" ^
  "$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10);" ^
  "Register-ScheduledTask -TaskName 'WorkBuddy_DailyCredits' -Action $action -Trigger @($t1,$t2) -Settings $s -User 'WeTrial' -Description 'WorkBuddy daily credits 12:00 + login' -Force | Out-Null;" ^
  "Write-Output 'Task created successfully'"

if errorlevel 1 (
    echo [ERROR] Failed to create scheduled task.
    echo Try running this script as Administrator.
    pause
    exit /b 1
)
echo.
echo Scheduled task created: daily at 12:00 + login catch-up
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
echo - Daily at 12:00, auto-claim 100 credits
echo - On login: catch-up if 12:00 was missed
echo - No need to open WorkBuddy, runs in background
echo - Log file: %~dp0claim_credits.log
echo - Re-login:  "%PYTHON%" "%SCRIPT%" --login
echo - Manual run: "%PYTHON%" "%SCRIPT%"
echo.
pause
endlocal
