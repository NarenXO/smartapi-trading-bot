import logging
from datetime import timedelta
from typing import Dict, Any, List, Set, Optional
from src.market_clock import MarketClock
from src.config import Config

logger = logging.getLogger(__name__)

# Map Nifty 50 symbols to broad sector buckets (static classification, not price simulation)
SYMBOL_SECTOR = {
    "RELIANCE": "ENERGY", "BPCL": "ENERGY", "IOC": "ENERGY", "ONGC": "ENERGY", "COALINDIA": "ENERGY",
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "TECHM": "IT", "WIPRO": "IT", "LTIM": "IT",
    "HDFCBANK": "BANK", "ICICIBANK": "BANK", "SBIN": "BANK", "KOTAKBANK": "BANK", "AXISBANK": "BANK", "INDUSINDBK": "BANK",
    "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG", "TATACONSUM": "FMCG",
    "TATAMOTORS": "AUTO", "M&M": "AUTO", "MARUTI": "AUTO", "HEROMOTOCO": "AUTO", "EICHERMOT": "AUTO",
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA", "DIVISLAB": "PHARMA", "APOLLOHOSP": "PHARMA",
    "TATASTEEL": "METAL", "JSWSTEEL": "METAL", "HINDALCO": "METAL",
    "LT": "INFRA", "ADANIPORTS": "INFRA", "ULTRACEMCO": "INFRA", "GRASIM": "INFRA",
    "BHARTIARTL": "TELECOM",
    "BAJFINANCE": "FINANCIALS", "BAJAJFINSV": "FINANCIALS", "HDFCLIFE": "FINANCIALS", "SBILIFE": "FINANCIALS",
    "NTPC": "POWER", "POWERGRID": "POWER",
    "ADANIENT": "CONGLOMERATE", "TITAN": "CONSUMER", "ASIANPAINT": "CONSUMER",
}

# Proxy index symbols available on NSE via instrument master names (EQ indices often under different tokens)
SECTOR_INDEX_SYMBOLS = {
    "BANK": "NIFTY BANK",
    "IT": "NIFTY IT",
    "AUTO": "NIFTY AUTO",
    "PHARMA": "NIFTY PHARMA",
    "FMCG": "NIFTY FMCG",
    "METAL": "NIFTY METAL",
    "ENERGY": "NIFTY ENERGY",
    "FINANCIALS": "NIFTY FIN SERVICE",
    "INFRA": "NIFTY INFRA",
    "POWER": "NIFTY ENERGY",
    "TELECOM": "NIFTY IT",
    "CONSUMER": "NIFTY FMCG",
    "CONGLOMERATE": "NIFTY 50",
}

class SectorRotationEngine:
    def __init__(self, fetcher, inst_mgr):
        self.fetcher = fetcher
        self.inst_mgr = inst_mgr
        self._top_sectors: Set[str] = set()
        self._scores: Dict[str, float] = {}

    def _resolve_index_token(self, label: str) -> Optional[str]:
        # Try common Angel instrument name fields via InstrumentManager dataframe if present
        try:
            df = getattr(self.inst_mgr, "df_instruments", None)
            if df is None or df.empty:
                return None
            # Prefer INDICES segment when available
            for col_name in ("name", "symbol"):
                if col_name not in df.columns:
                    continue
                match = df[df[col_name].astype(str).str.upper() == label.upper()]
                if not match.empty:
                    # Prefer NSE/NFO index rows
                    if "exch_seg" in match.columns:
                        pref = match[match["exch_seg"].isin(["NSE", "INDICES", "NFO"])]
                        if not pref.empty:
                            return str(pref.iloc[0]["token"])
                    return str(match.iloc[0]["token"])
            # Fuzzy contains
            if "name" in df.columns:
                fuzzy = df[df["name"].astype(str).str.upper().str.contains(label.upper().replace("NIFTY ", "NIFTY"), na=False)]
                if not fuzzy.empty:
                    return str(fuzzy.iloc[0]["token"])
        except Exception as e:
            logger.warning(f"SECTOR_TOKEN_RESOLVE_FAIL_{label}: {e}")
        return None

    def refresh(self) -> Dict[str, float]:
        now = MarketClock.now_ist()
        from_dt = (now - timedelta(days=10)).strftime("%Y-%m-%d 09:15")
        to_dt = now.strftime("%Y-%m-%d %H:%M")
        scores: Dict[str, float] = {}

        unique_labels = {}
        for sector, label in SECTOR_INDEX_SYMBOLS.items():
            unique_labels.setdefault(label, []).append(sector)

        for label, sectors in unique_labels.items():
            token = self._resolve_index_token(label)
            if not token:
                continue
            try:
                df = self.fetcher.fetch_candles(token, "ONE_DAY", from_dt, to_dt, exchange="NSE")
                if df is None or len(df) < 6:
                    # Try INDICES exchange segment if supported by fetcher signature
                    try:
                        df = self.fetcher.fetch_candles(token, "ONE_DAY", from_dt, to_dt, exchange="NSE")
                    except TypeError:
                        pass
                if df is not None and len(df) >= 6:
                    c0 = float(df.iloc[-6]["close"])
                    c1 = float(df.iloc[-1]["close"])
                    if c0 > 0:
                        roc = ((c1 - c0) / c0) * 100.0
                        for s in sectors:
                            scores[s] = roc
            except Exception as e:
                logger.warning(f"SECTOR_ROC_FAIL_{label}: {e}")

        self._scores = scores
        if scores:
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            top = [s for s, _ in ranked[: Config.TOP_SECTORS_COUNT]]
            self._top_sectors = set(top)
            logger.info(f"SECTOR_TOP_{Config.TOP_SECTORS_COUNT}: {top} SCORES={ranked[:5]}")
        else:
            # Fail-open: allow all sectors if indices unresolved
            self._top_sectors = set(SYMBOL_SECTOR.values())
            logger.warning("SECTOR_ROTATION_UNAVAILABLE_FAIL_OPEN_ALL")
        return scores

    def allows_symbol(self, symbol: str) -> Dict[str, Any]:
        if not Config.SECTOR_ROTATION_FILTER:
            return {"allowed": True, "reason": "SECTOR_FILTER_OFF", "sector": SYMBOL_SECTOR.get(symbol, "UNKNOWN")}
        if not self._top_sectors:
            self.refresh()
        sector = SYMBOL_SECTOR.get(symbol.upper(), "UNKNOWN")
        if sector == "UNKNOWN":
            return {"allowed": True, "reason": "SECTOR_UNKNOWN_FAIL_OPEN", "sector": sector}
        allowed = sector in self._top_sectors
        reason = f"SECTOR_OK_{sector}" if allowed else f"SECTOR_BLOCK_{sector}_NOT_IN_TOP"
        return {"allowed": allowed, "reason": reason, "sector": sector, "top": list(self._top_sectors)}
