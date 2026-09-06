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
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Telegram API response error: {response.text}")
        except requests.exceptions.Timeout:
            logger.warning("Telegram alert timed out (network latency). Trading loop unaffected.")
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")
