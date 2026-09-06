import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_KEY = os.getenv("ANGEL_API_KEY", "")
    CLIENT_CODE = os.getenv("ANGEL_CLIENT_CODE", "")
    PIN = os.getenv("ANGEL_PIN", "")
    TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "")
    
    DEFAULT_CAPITAL = float(os.getenv("DEFAULT_CAPITAL", "50000"))
    DEFAULT_RISK_PER_TRADE_PCT = float(os.getenv("DEFAULT_RISK_PER_TRADE_PCT", "1.0"))
    MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))
    
    TARGET_SYMBOLS = [
        s.strip() for s in os.getenv("TARGET_SYMBOLS", "RELIANCE,TCS,HDFCBANK").split(",") if s.strip()
    ]
    
    # Cost & Tax Structure (NSE Equities Intraday / Swing estimates)
    BROKERAGE_PER_ORDER = 20.0  # ₹20 flat or 0.03% (Angel One standard)
    STT_PCT_INTRADAY = 0.00025  # 0.025% on sell side
    EXCHANGE_TURNOVER_PCT = 0.0000345 # 0.00345%
    GST_PCT = 0.18 # 18% on (brokerage + turnover)
    STAMP_DUTY_BUY_PCT = 0.00003 # 0.003% on buy

    @classmethod
    def validate_creds(cls) -> bool:
        return bool(cls.API_KEY and cls.CLIENT_CODE and cls.PIN and cls.TOTP_SECRET)
