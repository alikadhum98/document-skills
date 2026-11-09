@echo off
cd /d "%~dp0"
echo [1/3] Installing components...
python -m pip install --upgrade pip
python -m pip install faster-whisper sounddevice numpy
echo [2/3] Downloading the speech model...
python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8'); print('MODEL OK')"
echo [3/3] Setting automatic start with Windows...
set "SU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LiveEar.bat"
(echo @echo off& echo start "Live Ear" /min python "%~dp0live_ear.py" --standby) > "%SU%"
start "" "%SU%"
echo.
echo READY. Live Ear now waits in the background and starts with Windows.
pause
