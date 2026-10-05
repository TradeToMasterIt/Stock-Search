@echo off
title Patel Trading Bot - Auto Scanner
cd /d "%~dp0"
echo ========================================================
echo   PATEL TRADING BOT - AUTO SCANNER (LIVE MARKET)
echo ========================================================
echo Starting scanner... Alerts will be sent to Telegram!
python auto_scanner.py
pause
