import pyotp
import logging
from typing import Optional
from SmartApi import SmartConnect
from src.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class SmartAPIAuth:
    def __init__(self):
        self.api_key = Config.API_KEY
        self.client_code = Config.CLIENT_CODE
        self.pin = Config.PIN
        self.totp_secret = Config.TOTP_SECRET
        self.smart_api: Optional[SmartConnect] = None
        self.auth_data: Optional[dict] = None

    def generate_totp(self) -> str:
        """Generates real-time 6-digit TOTP code using secret."""
        if not self.totp_secret:
            raise ValueError("TOTP Secret is not configured in .env")
        totp = pyotp.TOTP(self.totp_secret)
        return totp.now()

    def login(self) -> Optional[SmartConnect]:
        """Authenticates with Angel One SmartAPI and initializes session."""
        if not Config.validate_creds():
            logger.warning("SmartAPI credentials not fully configured in .env.")
            return None

        try:
            totp_code = self.generate_totp()
            self.smart_api = SmartConnect(api_key=self.api_key)
            self.auth_data = self.smart_api.generateSession(
                clientCode=self.client_code,
                password=self.pin,
                totp=totp_code
            )
            
            if self.auth_data and self.auth_data.get("status"):
                logger.info(f"SmartAPI login successful for Client: {self.client_code}")
                return self.smart_api
            else:
                logger.error(f"SmartAPI login failed: {self.auth_data.get('message', 'Unknown error')}")
                return None
        except Exception as e:
            logger.error(f"Exception during SmartAPI authentication: {str(e)}")
            return None

    def get_feed_token(self) -> Optional[str]:
        if self.auth_data and self.auth_data.get("data"):
            return self.auth_data["data"].get("feedToken")
        return None
