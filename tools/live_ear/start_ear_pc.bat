@echo off
title Live Ear PC
rem Starts the PC ear. Keep this window open, you may minimize it.
:loop
python "%~dp0ear_local.py"
if %errorlevel%==0 goto end
echo Live Ear stopped unexpectedly. Starting again in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
:end
pause
