@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
if not exist "%ROOT%logs" mkdir "%ROOT%logs"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "STAMP=%%i"
set "LOG=%ROOT%logs\run_%STAMP%.log"
echo ==== %date% %time% : run start ==== >> "%LOG%"
"%ROOT%.venv\Scripts\python.exe" "%ROOT%run.py" --quiet >> "%LOG%" 2>&1
set "RC=%errorlevel%"
echo ==== %date% %time% : run end (exit %RC%) ==== >> "%LOG%"
endlocal ^& exit /b %RC%
