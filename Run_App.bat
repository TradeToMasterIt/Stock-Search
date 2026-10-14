@echo off
title Confluence Pro Trading Terminal
cd /d "%~dp0"
echo ========================================================
echo   CONFLUENCE PRO - TRADING TERMINAL
echo ========================================================
echo Starting Streamlit Web Application...
streamlit run app.py
pause
