@echo off
rem Manual mode with the more accurate, slower model (small.en).
rem If the program stops by itself, it starts again after 10 seconds.
rem To stop for good: press Ctrl+C, or close this window.
:loop
python "%~dp0live_ear.py" --model small.en %*
if %errorlevel%==0 goto end
echo.
echo Live Ear stopped unexpectedly. Starting again in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
:end
pause
