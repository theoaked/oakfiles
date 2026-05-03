@echo off
:: OakFiles Windows Service Installer
:: Requires NSSM (https://nssm.cc) to be available in PATH or same directory
:: Run as Administrator

setlocal

set SERVICE_NAME=OakFilesService
set PROJECT_DIR=%~dp0
set PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe

:: Verify the virtual environment exists
if not exist "%PYTHON%" (
    echo ERROR: .venv not found. Run setup first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo Installing %SERVICE_NAME%...
echo   Project dir : %PROJECT_DIR%
echo   Python      : %PYTHON%

:: Remove existing service if present
nssm stop %SERVICE_NAME% 2>nul
nssm remove %SERVICE_NAME% confirm 2>nul

:: Install new service
nssm install %SERVICE_NAME% "%PYTHON%" "main.py"
nssm set %SERVICE_NAME% AppDirectory "%PROJECT_DIR%"
nssm set %SERVICE_NAME% AppStdout "%PROJECT_DIR%logs\service.log"
nssm set %SERVICE_NAME% AppStderr "%PROJECT_DIR%logs\service.log"
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateOnline 1
nssm set %SERVICE_NAME% AppRotateBytes 10485760
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% DisplayName "OakFiles File Server"
nssm set %SERVICE_NAME% Description "OakFiles local network file storage"

echo.
echo Starting service...
nssm start %SERVICE_NAME%

echo.
echo Done. OakFiles is running as a Windows service.
echo To stop:    nssm stop %SERVICE_NAME%
echo To uninstall: nssm remove %SERVICE_NAME% confirm
pause
