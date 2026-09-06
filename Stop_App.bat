@echo off
title Stop Trading Bot
echo Stopping all running background bot processes...
call venv\Scripts\activate.bat
python -c "from src.bot_controller import BotController; BotController.stop_bot(); print('All bot processes stopped successfully.')"
pause
