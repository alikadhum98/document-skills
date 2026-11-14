@echo off
rem Strengthens microphone capture for Live Ear. Add the word restore to undo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0mic_boost.ps1" %1
pause
