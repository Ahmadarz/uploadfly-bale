@echo off
rem UploadFly for Bale: run the bot and the Mini App server on this PC (for testing).
rem Keep this window open while the bot should be running. Close it (or press Ctrl+C) to stop.
rem Never run this while the server copy is running with the same bot token.
title UploadFly (Bale)
cd /d "%~dp0bot"
if not exist ".env" (
  echo bot\.env is missing. Copy bot\.env.example to bot\.env and fill in BOT_TOKEN and ENCRYPTION_KEY.
  pause
  exit /b 1
)
set PYTHONUTF8=1
"..\.venv\Scripts\python.exe" -m app.main
echo.
echo UploadFly stopped.
pause
