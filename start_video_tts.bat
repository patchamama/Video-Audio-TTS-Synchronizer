@echo off
setlocal
set "ROOT=%~dp0"
set "REPO=https://raw.githubusercontent.com/patchamama/Video-Audio-TTS-Synchronizer/main"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

echo Checking Video TTS files...
if not exist "%ROOT%web" mkdir "%ROOT%web"
for %%F in (create_video_tts_from_srt.py requirements.txt) do (
  if exist "%ROOT%%%F" (echo Using local file: %%F) else (powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing '%REPO%/%%F' -OutFile '%ROOT%%%F'" || goto :error)
)
for %%F in (index.html styles.css app.js favicon.svg) do (
  if exist "%ROOT%web\%%F" (echo Using local file: web\%%F) else (powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing '%REPO%/web/%%F' -OutFile '%ROOT%web\%%F'" || goto :error)
)

if not exist "%PYTHON%" (
  echo Creating local virtual environment...
  py -3 -m venv "%ROOT%.venv" || goto :error
)

"%PYTHON%" -m pip install --upgrade pip || goto :error
"%PYTHON%" -m pip install -r "%ROOT%requirements.txt" || goto :error

if "%~1"=="" (
  "%PYTHON%" "%ROOT%create_video_tts_from_srt.py" --web
) else (
  "%PYTHON%" "%ROOT%create_video_tts_from_srt.py" %*
)
exit /b %ERRORLEVEL%

:error
echo Failed to download, create the virtual environment, or install requirements.
exit /b 1
