import os
import json
import logging
import requests
import pandas as pd
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class InstrumentManager:
    SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    CACHE_FILE = "data/scrip_master.json"

    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self.df_instruments: Optional[pd.DataFrame] = None
        self.load_instruments()

    def download_scrip_master(self) -> bool:
        """Downloads latest instrument list from Angel One."""
        try:
            logger.info("Downloading latest OpenAPIScripMaster from Angel One...")
            response = requests.get(self.SCRIP_MASTER_URL, timeout=30)
            if response.status_code == 200:
                with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(response.text)
                logger.info("OpenAPIScripMaster downloaded and cached.")
                return True
            else:
                logger.error(f"Failed to download scrip master: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error downloading scrip master: {str(e)}")
            return False

    def load_instruments(self):
        """Loads cached scrip master or downloads if missing."""
        if not os.path.exists(self.CACHE_FILE):
            success = self.download_scrip_master()
            if not success:
                logger.warning("Using empty instruments cache.")
                self.df_instruments = pd.DataFrame()
                return

        try:
            with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.df_instruments = pd.DataFrame(data)
            logger.info(f"Loaded {len(self.df_instruments)} instruments from cache.")
        except Exception as e:
            logger.error(f"Failed to parse instruments cache: {str(e)}")
            self.df_instruments = pd.DataFrame()

    def get_token(self, symbol: str, exch_seg: str = "NSE") -> Optional[str]:
        """
        Looks up token for a given symbol (e.g. 'RELIANCE' -> 'RELIANCE-EQ').
        """
        if self.df_instruments is None or self.df_instruments.empty:
            return None

        # Clean symbol format for equity search
        formatted_symbol = symbol.strip().upper()
        if not formatted_symbol.endswith("-EQ") and exch_seg == "NSE":
            lookup_symbol = f"{formatted_symbol}-EQ"
        else:
            lookup_symbol = formatted_symbol

        match = self.df_instruments[
            (self.df_instruments['exch_seg'] == exch_seg) & 
            (self.df_instruments['symbol'] == lookup_symbol)
        ]

        if not match.empty:
            return str(match.iloc[0]['token'])
        
        # Fallback: exact match on name
        fallback_match = self.df_instruments[
            (self.df_instruments['exch_seg'] == exch_seg) & 
            (self.df_instruments['name'] == formatted_symbol)
        ]
        if not fallback_match.empty:
            return str(fallback_match.iloc[0]['token'])

        return None
