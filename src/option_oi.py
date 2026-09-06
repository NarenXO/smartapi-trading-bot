import logging
from typing import Dict, Any, Optional, List
import requests

logger = logging.getLogger(__name__)

class OptionOIAnalyzer:
    """
    Nifty option-chain OI wall detector using NSE free option-chain API.
    Support = strike with max Put OI; Resistance = strike with max Call OI.
    """
    CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/option-chain",
    }

    @classmethod
    def fetch_nifty_walls(cls) -> Dict[str, Any]:
        session = requests.Session()
        try:
            session.get("https://www.nseindia.com", headers=cls.HEADERS, timeout=10)
            session.get("https://www.nseindia.com/option-chain", headers=cls.HEADERS, timeout=10)
            resp = session.get(cls.CHAIN_URL, headers=cls.HEADERS, timeout=15)
            if resp.status_code != 200:
                return {"status": "unavailable", "spot": 0.0, "support": 0.0, "resistance": 0.0}

            payload = resp.json()
            records = payload.get("records", {})
            spot = float(records.get("underlyingValue", 0) or 0)
            data: List[dict] = records.get("data", []) or []

            max_pe_oi = -1
            max_ce_oi = -1
            support = 0.0
            resistance = 0.0

            for row in data:
                strike = float(row.get("strikePrice", 0) or 0)
                pe = row.get("PE") or {}
                ce = row.get("CE") or {}
                pe_oi = float(pe.get("openInterest", 0) or 0)
                ce_oi = float(ce.get("openInterest", 0) or 0)
                if pe_oi > max_pe_oi:
                    max_pe_oi = pe_oi
                    support = strike
                if ce_oi > max_ce_oi:
                    max_ce_oi = ce_oi
                    resistance = strike

            return {
                "status": "ok",
                "spot": spot,
                "support": support,
                "resistance": resistance,
                "max_pe_oi": max_pe_oi,
                "max_ce_oi": max_ce_oi,
            }
        except Exception as e:
            logger.error(f"OPTION_OI_ERROR: {e}")
            return {"status": "unavailable", "spot": 0.0, "support": 0.0, "resistance": 0.0}

    @classmethod
    def long_bias_ok(cls, buffer_pct: float = 0.15) -> Dict[str, Any]:
        """
        Allow longs if spot is not pinned into call-wall resistance within buffer_pct.
        Fail-open if data unavailable.
        """
        walls = cls.fetch_nifty_walls()
        if walls["status"] != "ok" or walls["spot"] <= 0:
            return {"allowed": True, "reason": "OPTION_OI_UNAVAILABLE_FAIL_OPEN", "walls": walls}

        spot = walls["spot"]
        res = walls["resistance"]
        sup = walls["support"]
        # If resistance is very close above spot, treat as crowded call wall risk
        if res > 0 and spot > 0:
            dist_to_res_pct = ((res - spot) / spot) * 100
            if 0 <= dist_to_res_pct <= buffer_pct:
                return {
                    "allowed": False,
                    "reason": f"OPTION_OI_NEAR_CALL_WALL_SPOT_{spot}_RES_{res}",
                    "walls": walls,
                }
        return {
            "allowed": True,
            "reason": f"OPTION_OI_OK_SPOT_{spot}_SUP_{sup}_RES_{res}",
            "walls": walls,
        }
