import logging
import requests
from src.config import Config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    @staticmethod
    def send_message(message: str):
        token = Config.TELEGRAM_BOT_TOKEN
        chat_id = Config.TELEGRAM_CHAT_ID
        if not token or not chat_id:
            return
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")
