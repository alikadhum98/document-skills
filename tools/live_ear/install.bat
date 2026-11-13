@echo off
set "APP=%USERPROFILE%\LiveEar"
if not exist "%APP%" mkdir "%APP%"
copy /Y "%~dp0live_ear.py" "%APP%\" >nul
echo [1/3] Installing components...
python -m pip install --upgrade pip
python -m pip install faster-whisper sounddevice numpy
echo [2/3] Downloading the speech models...
python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8'); WhisperModel('small.en', device='cpu', compute_type='int8'); print('MODELS OK')"
echo [3/3] Setting automatic start with Windows...
taskkill /FI "WINDOWTITLE eq Live Ear*" /T /F >nul 2>&1
set "RUN=%APP%\run_standby.bat"
> "%RUN%" echo @echo off
>> "%RUN%" echo title Live Ear
>> "%RUN%" echo :loop
>> "%RUN%" echo python "%APP%\live_ear.py" --standby
>> "%RUN%" echo echo Live Ear stopped. Starting again in 15 seconds...
>> "%RUN%" echo timeout /t 15 /nobreak ^>nul
>> "%RUN%" echo goto loop
set "SU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LiveEar.bat"
> "%SU%" echo @echo off
>> "%SU%" echo start "Live Ear" /min "%RUN%"
start "" "%SU%"
echo.
echo READY. Live Ear now waits in the background, starts with Windows,
echo and starts again by itself if it ever stops.
pause
