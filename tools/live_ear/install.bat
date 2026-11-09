@echo off
echo Installing live ear...
python -m pip install --upgrade pip
python -m pip install faster-whisper sounddevice numpy
python -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8'); print('READY')"
pause
