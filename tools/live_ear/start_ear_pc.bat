@echo off
rem Starts the PC ear in the background, without a console window.
where pythonw >nul 2>&1
if %errorlevel%==0 (
  start "" pythonw "%~dp0ear_local.py"
) else (
  start "Live Ear" /min python "%~dp0ear_local.py"
)
exit
