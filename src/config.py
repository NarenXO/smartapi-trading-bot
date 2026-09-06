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

    # Live Trading Safety Controls
    DRY_RUN = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")
    MAX_QTY_PER_TRADE = int(os.getenv("MAX_QTY_PER_TRADE", "1"))
    MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
    ORDER_TYPE = os.getenv("ORDER_TYPE", "MARKET")

    # Phase 7: Advanced Risk & Strategy Controls
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "1.5"))
    TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "3.0"))
    MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
    COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "15"))
    ATR_MIN_PCT = float(os.getenv("ATR_MIN_PCT", "0.1"))

    # Phase 8: Production Hardening
    TRAILING_SL_PCT = float(os.getenv("TRAILING_SL_PCT", "1.0"))
    AUTO_SQUARE_OFF_HOUR = int(os.getenv("AUTO_SQUARE_OFF_HOUR", "15"))
    AUTO_SQUARE_OFF_MINUTE = int(os.getenv("AUTO_SQUARE_OFF_MINUTE", "15"))

    # Phase 9: Dynamic Universe & Predictive Confluence
    UNIVERSE_MODE = os.getenv("UNIVERSE_MODE", "NIFTY50") # NIFTY50 or STATIC
    CONFLUENCE_THRESHOLD = float(os.getenv("CONFLUENCE_THRESHOLD", "0.80")) # 80% score required
    MAX_SCAN_SYMBOLS = int(os.getenv("MAX_SCAN_SYMBOLS", "50")) # Scan all for ranking
    TOP_K_STOCKS = int(os.getenv("TOP_K_STOCKS", "5")) # Only actively trade top 5

    # Phase 10: Enterprise Quant Settings
    MARKET_REGIME_FILTER = os.getenv("MARKET_REGIME_FILTER", "True").lower() in ("true", "1", "yes")
    MAX_SPREAD_PCT = float(os.getenv("MAX_SPREAD_PCT", "0.20")) # 0.20% max allowed spread
    RISK_PER_TRADE_FRACTION = float(os.getenv("RISK_PER_TRADE_FRACTION", "0.01")) # 1% account risk per trade
    NIFTY_TOKEN = "99926000" # NSE Nifty 50 Token
    
    # Cost & Tax Structure (NSE Equities Intraday / Swing estimates)
    BROKERAGE_PER_ORDER = 20.0  # ₹20 flat or 0.03% (Angel One standard)
    STT_PCT_INTRADAY = 0.00025  # 0.025% on sell side
    EXCHANGE_TURNOVER_PCT = 0.0000345 # 0.00345%
    GST_PCT = 0.18 # 18% on (brokerage + turnover)
    STAMP_DUTY_BUY_PCT = 0.00003 # 0.003% on buy

    @classmethod
    def validate_creds(cls) -> bool:
        return bool(cls.API_KEY and cls.CLIENT_CODE and cls.PIN and cls.TOTP_SECRET)
