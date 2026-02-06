@echo off
REM Setup scheduled task for API metadata update
REM Runs at 8pm today, repeats every 2 hours until Sunday midnight

echo Creating scheduled task for API metadata update...

REM Get Python path
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i

REM Delete existing task if it exists
schtasks /delete /tn "RegCost_API_Update" /f 2>nul

REM Create the task
REM - Starts at 8pm today
REM - Repeats every 2 hours for 48 hours (covers the weekend)
REM - Runs whether user is logged on or not (if admin)
schtasks /create ^
    /tn "RegCost_API_Update" ^
    /tr "\"%PYTHON_PATH%\" \"C:\Users\joelr\projects\regcost\scheduled_api_update.py\"" ^
    /sc once ^
    /st 20:00 ^
    /ri 120 ^
    /du 48:00 ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Task created successfully!
    echo.
    echo Task details:
    schtasks /query /tn "RegCost_API_Update" /v /fo list | findstr /i "TaskName Status Next"
    echo.
    echo The task will:
    echo   - Start at 8:00 PM today
    echo   - Retry every 2 hours if API is unavailable
    echo   - Run for up to 48 hours ^(covers the weekend^)
    echo   - Stop automatically when update completes
    echo.
    echo Log file: C:\Users\joelr\projects\regcost\logs\api_update.log
    echo Completion marker: C:\Users\joelr\projects\regcost\data\api_update_complete.json
) else (
    echo.
    echo Failed to create task. You may need to run as Administrator.
)

pause
