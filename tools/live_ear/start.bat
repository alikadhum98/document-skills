@echo off
set OUT=%USERPROFILE%\Desktop\COP31_live.txt
for %%D in (G H I J K) do if exist "%%D:\My Drive" set OUT=%%D:\My Drive\COP31_live.txt
echo Writing to %OUT%
python "%~dp0live_ear.py" --out "%OUT%" %*
pause
