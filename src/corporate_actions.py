import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Set
import pandas as pd
from src.market_clock import MarketClock
from src.config import Config

logger = logging.getLogger(__name__)

class CorporateActionsFilter:
    DEFAULT_PATH = "data/corporate_actions.csv"

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._blocked_today: Set[str] = set()
        self.reload()

    def reload(self):
        self._blocked_today = set()
        if not Config.CORPORATE_ACTIONS_FILTER:
            return
        if not os.path.exists(self.path):
            logger.warning("CORPORATE_ACTIONS_FILE_MISSING")
            return
        try:
            df = pd.read_csv(self.path)
            if df.empty:
                return
            today = MarketClock.now_ist().date()
            for _, row in df.iterrows():
                sym = str(row.get("symbol", "")).strip().upper()
                ed = str(row.get("event_date", "")).strip()
                if not sym or not ed or ed.startswith("2099"):
                    continue
                try:
                    event_day = datetime.strptime(ed, "%Y-%m-%d").date()
                except Exception:
                    continue
                # Pause from T-1 through T+0
                if (event_day - timedelta(days=1)) <= today <= event_day:
                    self._blocked_today.add(sym)
            logger.info(f"CORPORATE_ACTIONS_BLOCKED_TODAY: {sorted(self._blocked_today)}")
        except Exception as e:
            logger.error(f"CORPORATE_ACTIONS_LOAD_ERROR: {e}")

    def allows_symbol(self, symbol: str) -> Dict[str, Any]:
        if not Config.CORPORATE_ACTIONS_FILTER:
            return {"allowed": True, "reason": "CORP_ACTIONS_FILTER_OFF"}
        sym = symbol.upper()
        if sym in self._blocked_today:
            return {"allowed": False, "reason": f"CORP_ACTION_PAUSE_{sym}"}
        return {"allowed": True, "reason": "CORP_ACTION_CLEAR"}
