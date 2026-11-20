@echo off
rem Installs what the PC ear needs, once: room recording, gap recovery and automatic language.
rem It no longer installs the old standby ear, and removes it if an earlier version did.
echo [1/3] Installing components...
python -m pip install --upgrade pip
python -m pip install faster-whisper sounddevice numpy
if errorlevel 1 goto failed
echo [2/3] Downloading the speech models (once only, this can take several minutes)...
python -c "from faster_whisper import WhisperModel; [WhisperModel(m, device='cpu', compute_type='int8') for m in ('small.en', 'base', 'small')]; print('MODELS OK')"
if errorlevel 1 goto failed
echo [3/3] Removing the old standby ear...
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LiveEar.bat" del /F /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LiveEar.bat"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -match 'run_standby\.bat' -or ($_.CommandLine -match 'live_ear\.py' -and $_.CommandLine -match '--standby')) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo.
echo READY. Now double-click start_ear_pc.bat to open the ear.
pause
exit /b 0
:failed
echo.
echo SOMETHING FAILED above. Check the internet connection and that Python is installed, then run install.bat again.
pause
exit /b 1
