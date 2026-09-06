@echo off
title Angel One Trading Bot Dashboard
echo Starting Angel One Trading Bot Web Interface...
call venv\Scripts\activate.bat
streamlit run dashboard.py
pause
