@echo off
rem Manual mode with the more accurate, slower model.
python "%~dp0live_ear.py" --model small.en %*
pause
