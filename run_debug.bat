@echo off
setlocal
cd /d "%~dp0"
set ADDRESS_MATCHER_DEBUG=1
python main.py --debug
echo.
echo Debug logs are in: %~dp0logs
pause
