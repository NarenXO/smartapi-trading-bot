import logging
from typing import List, Dict
from src.instruments import InstrumentManager
from src.config import Config

logger = logging.getLogger(__name__)

NIFTY_50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", 
    "SBIN", "BHARTIARTL", "LTIM", "KOTAKBANK", "LT", "AXISBANK", "HCLTECH", 
    "ASIANPAINT", "TITAN", "MARUTI", "SUNPHARMA", "BAJFINANCE", "ULTRACEMCO", 
    "TATASTEEL", "NTPC", "POWERGRID", "M&M", "TATAMOTORS", "ADANIENT", 
    "ADANIPORTS", "COALINDIA", "BAJAJFINSV", "BPCL", "GRASIM", "HEROMOTOCO", 
    "HDFCLIFE", "HINDALCO", "INDUSINDBK", "IOC", "JSWSTEEL", "NESTLEIND", 
    "ONGC", "DRREDDY", "EICHERMOT", "CIPLA", "TATACONSUM", "BRITANNIA", 
    "SBILIFE", "APOLLOHOSP", "TECHM", "WIPRO", "DIVISLAB"
]

class UniverseScanner:
    def __init__(self):
        self.inst_mgr = InstrumentManager()

    def get_target_tokens(self) -> Dict[str, str]:
        """Returns token map for Nifty 50 or configured target symbols."""
        symbol_list = NIFTY_50_SYMBOLS if Config.UNIVERSE_MODE == "NIFTY50" else Config.TARGET_SYMBOLS
        symbol_list = symbol_list[:Config.MAX_SCAN_SYMBOLS]
        
        token_map = {}
        for sym in symbol_list:
            token = self.inst_mgr.get_token(sym, "NSE")
            if token:
                token_map[sym] = token
                
        logger.info(f"UNIVERSE_LOADED_SYMBOLS_COUNT: {len(token_map)} (MODE: {Config.UNIVERSE_MODE})")
        return token_map
