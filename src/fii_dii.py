import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

class FIIDIIClient:
    """
    Fetches latest FII/DII cash-market net flow from NSE public API.
    Returns structured dict. On failure returns status=unavailable (caller decides fail-open/closed).
    """
    NSE_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/reports/fii-dii",
    }

    @classmethod
    def fetch_latest(cls) -> Dict[str, Any]:
        session = requests.Session()
        try:
            # Warm-up cookies
            session.get("https://www.nseindia.com", headers=cls.HEADERS, timeout=10)
            session.get("https://www.nseindia.com/reports/fii-dii", headers=cls.HEADERS, timeout=10)
            resp = session.get(cls.NSE_URL, headers=cls.HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"FII_DII_HTTP_{resp.status_code}")
                return {"status": "unavailable", "fii_net": 0.0, "dii_net": 0.0, "combined_net": 0.0, "raw": None}

            data = resp.json()
            # NSE payload is typically a list of category rows with buyValue/sellValue/netValue
            fii_net = 0.0
            dii_net = 0.0
            if isinstance(data, list):
                for row in data:
                    cat = str(row.get("category", "") or row.get("Category", "")).upper()
                    net_raw = row.get("netValue", row.get("net", row.get("NetValue", 0)))
                    try:
                        net = float(str(net_raw).replace(",", ""))
                    except Exception:
                        net = 0.0
                    if "FII" in cat or "FPI" in cat:
                        fii_net = net
                    elif "DII" in cat:
                        dii_net = net
            elif isinstance(data, dict):
                # Alternate shapes
                fii_net = float(data.get("fii_net", data.get("fiiNet", 0)) or 0)
                dii_net = float(data.get("dii_net", data.get("diiNet", 0)) or 0)

            combined = fii_net + dii_net
            return {
                "status": "ok",
                "fii_net": round(fii_net, 2),
                "dii_net": round(dii_net, 2),
                "combined_net": round(combined, 2),
                "raw": data,
            }
        except Exception as e:
            logger.error(f"FII_DII_FETCH_ERROR: {e}")
            return {"status": "unavailable", "fii_net": 0.0, "dii_net": 0.0, "combined_net": 0.0, "raw": None}

    @classmethod
    def allows_longs(cls, min_combined_crore: float = 0.0) -> Dict[str, Any]:
        snap = cls.fetch_latest()
        if snap["status"] != "ok":
            # Fail-open on data outage so bot does not freeze entirely; log clearly
            return {"allowed": True, "reason": "FII_DII_DATA_UNAVAILABLE_FAIL_OPEN", "snapshot": snap}
        allowed = snap["combined_net"] >= min_combined_crore
        reason = (
            f"FII_DII_OK_COMBINED_{snap['combined_net']}"
            if allowed
            else f"FII_DII_BLOCK_COMBINED_{snap['combined_net']}_LT_{min_combined_crore}"
        )
        return {"allowed": allowed, "reason": reason, "snapshot": snap}
