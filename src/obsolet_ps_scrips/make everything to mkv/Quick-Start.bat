@echo off
setlocal enabledelayedexpansion
REM Quick Start Batch File for Movie Converter
REM Forces PowerShell 7 if available, falls back to Windows PowerShell

echo ========================================================
echo   Movie to MKV Converter - Quick Start
echo ========================================================
echo.

REM Try to find PowerShell 7 in common locations
set "PWSH_PATH="

REM Check PATH first
where pwsh.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PWSH_PATH=pwsh.exe"
    goto :FOUND_PWSH
)

REM Check common installation paths
if exist "C:\Program Files\PowerShell\7\pwsh.exe" (
    set "PWSH_PATH=C:\Program Files\PowerShell\7\pwsh.exe"
    goto :FOUND_PWSH
)

if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
    set "PWSH_PATH=%ProgramFiles%\PowerShell\7\pwsh.exe"
    goto :FOUND_PWSH
)

if exist "%LocalAppData%\Microsoft\PowerShell\7\pwsh.exe" (
    set "PWSH_PATH=%LocalAppData%\Microsoft\PowerShell\7\pwsh.exe"
    goto :FOUND_PWSH
)

REM PowerShell 7 not found
echo PowerShell 7 not found. Using Windows PowerShell 5.1...
echo [WARNING: Parallel processing NOT available - will be slower]
echo [Install PowerShell 7 for 2-4x faster conversion]
echo.
set "PS_CMD=powershell.exe"
set "SCRIPT_NAME=Convert-MoviesToMKV-WinPS.ps1"
goto :SHOW_MENU

:FOUND_PWSH
echo Found PowerShell 7 - Using parallel processing!
set "PS_CMD=!PWSH_PATH!"
set "SCRIPT_NAME=Convert-MoviesToMKV-Optimized-Fixed.ps1"

:SHOW_MENU
echo.
echo Select an option:
echo.
echo 1. Convert Y:\ (default settings)
echo 2. Convert Y:\ (fast - 4 parallel jobs) [PowerShell 7 only]
echo 3. Convert custom path
echo 4. Test run (no delete originals)
echo 5. Direct NAS conversion (no local temp)
echo 6. Install/Update PowerShell 7
echo 7. Exit
echo.

set /p choice="Enter choice (1-7): "

if "%choice%"=="1" (
    echo.
    echo Running with default settings...
    "!PS_CMD!" -ExecutionPolicy Bypass -NoProfile -File "%~dp0!SCRIPT_NAME!" -RootPath "Y:\"
    goto END
)

if "%choice%"=="2" (
    echo.
    if "!SCRIPT_NAME!"=="Convert-MoviesToMKV-WinPS.ps1" (
        echo ERROR: Parallel processing requires PowerShell 7!
        echo PowerShell 7 was not found on your system.
        echo.
        echo Please choose option 6 to install PowerShell 7,
        echo or choose option 1 for sequential processing.
        echo.
        pause
        goto END
    )
    echo Running with 4 parallel jobs...
    "!PS_CMD!" -ExecutionPolicy Bypass -NoProfile -File "%~dp0!SCRIPT_NAME!" -RootPath "Y:\" -MaxParallelJobs 4
    goto END
)

if "%choice%"=="3" (
    set /p "custompath=Enter path (e.g., C:\Movies): "
    echo.
    echo Converting: !custompath!
    "!PS_CMD!" -ExecutionPolicy Bypass -NoProfile -File "%~dp0!SCRIPT_NAME!" -RootPath "!custompath!"
    goto END
)

if "%choice%"=="4" (
    echo.
    echo Test run - originals will NOT be deleted...
    "!PS_CMD!" -ExecutionPolicy Bypass -NoProfile -File "%~dp0!SCRIPT_NAME!" -RootPath "Y:\" -DeleteOriginal $false
    goto END
)

if "%choice%"=="5" (
    echo.
    echo Direct NAS conversion (slower but no local disk space needed)...
    "!PS_CMD!" -ExecutionPolicy Bypass -NoProfile -File "%~dp0!SCRIPT_NAME!" -RootPath "Y:\" -UseLocalConversion $false
    goto END
)

if "%choice%"=="6" (
    echo.
    echo Installing/Updating PowerShell 7...
    echo.
    echo Attempting installation via winget...
    winget install Microsoft.PowerShell --silent
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo PowerShell 7 installed successfully!
        echo Please RESTART this batch file to use it.
        echo.
    ) else (
        echo.
        echo Winget installation failed or winget not available.
        echo Opening download page in browser...
        start https://github.com/PowerShell/PowerShell/releases/latest
        echo.
        echo After installing, RESTART this batch file.
    )
    pause
    goto END
)

if "%choice%"=="7" (
    echo.
    echo Exiting...
    goto END
)

echo.
echo Invalid choice. Please run again.

:END
echo.
pause
endlocal
