import logging
from typing import Dict, Any
from src.config import Config
from src.fii_dii import FIIDIIClient
from src.option_oi import OptionOIAnalyzer

logger = logging.getLogger(__name__)

class InstitutionalGate:
    def __init__(self, sector_engine=None, corp_filter=None):
        self.sector_engine = sector_engine
        self.corp_filter = corp_filter
        self.last_macro: Dict[str, Any] = {}

    def refresh_macro(self) -> Dict[str, Any]:
        result = {
            "fii_dii": {"allowed": True, "reason": "OFF"},
            "option_oi": {"allowed": True, "reason": "OFF"},
        }
        if Config.FII_DII_FILTER:
            fii_result = FIIDIIClient.allows_longs(Config.FII_DII_MIN_NET_CRORE)
            # Handle data unavailability based on GATE_FAIL_MODE
            if fii_result.get("reason") in ["DATA_UNAVAILABLE", "FETCH_ERROR", "INSUFFICIENT_DATA"]:
                if Config.GATE_FAIL_MODE == "fail_closed":
                    fii_result = {"allowed": False, "reason": "DATA_UNAVAILABLE_FAIL_CLOSED"}
                    logger.warning("FII_DII_GATE_FAIL_CLOSED: Data unavailable, blocking trades")
                else:
                    fii_result = {"allowed": True, "reason": "DATA_UNAVAILABLE_FAIL_OPEN"}
                    logger.info("FII_DII_GATE_FAIL_OPEN: Data unavailable, allowing trades")
            logger.info(f"FII_DII_GATE: allowed={fii_result['allowed']}, reason={fii_result['reason']}")
            result["fii_dii"] = fii_result
        if Config.OPTION_OI_FILTER:
            oi_result = OptionOIAnalyzer.long_bias_ok(buffer_pct=0.20)
            # Handle data unavailability based on GATE_FAIL_MODE
            if oi_result.get("reason") in ["DATA_UNAVAILABLE", "FETCH_ERROR", "INSUFFICIENT_DATA"]:
                if Config.GATE_FAIL_MODE == "fail_closed":
                    oi_result = {"allowed": False, "reason": "DATA_UNAVAILABLE_FAIL_CLOSED"}
                    logger.warning("OPTION_OI_GATE_FAIL_CLOSED: Data unavailable, blocking trades")
                else:
                    oi_result = {"allowed": True, "reason": "DATA_UNAVAILABLE_FAIL_OPEN"}
                    logger.info("OPTION_OI_GATE_FAIL_OPEN: Data unavailable, allowing trades")
            logger.info(f"OPTION_OI_GATE: allowed={oi_result['allowed']}, reason={oi_result['reason']}")
            result["option_oi"] = oi_result
        self.last_macro = result
        return result

    def allows_long(self, symbol: str) -> Dict[str, Any]:
        reasons = []
        # Macro gates
        if not self.last_macro:
            self.refresh_macro()
        fii = self.last_macro.get("fii_dii", {"allowed": True, "reason": "NA"})
        oi = self.last_macro.get("option_oi", {"allowed": True, "reason": "NA"})
        if not fii.get("allowed", True):
            logger.info(f"SYMBOL_{symbol}_BLOCKED_FII_DII: {fii.get('reason')}")
            return {"allowed": False, "reason": fii.get("reason", "FII_DII_BLOCK")}
        if not oi.get("allowed", True):
            logger.info(f"SYMBOL_{symbol}_BLOCKED_OPTION_OI: {oi.get('reason')}")
            return {"allowed": False, "reason": oi.get("reason", "OPTION_OI_BLOCK")}

        if self.corp_filter is not None:
            c = self.corp_filter.allows_symbol(symbol)
            if not c.get("allowed", True):
                logger.info(f"SYMBOL_{symbol}_BLOCKED_CORP_ACTION: {c.get('reason')}")
                return c
            reasons.append(c.get("reason", ""))

        if self.sector_engine is not None:
            s = self.sector_engine.allows_symbol(symbol)
            if not s.get("allowed", True):
                logger.info(f"SYMBOL_{symbol}_BLOCKED_SECTOR_ROTATION: {s.get('reason')}")
                return s
            reasons.append(s.get("reason", ""))

        final_reason = "|".join([r for r in reasons if r]) or "INSTITUTIONAL_GATES_PASS"
        logger.info(f"SYMBOL_{symbol}_ALLOWED: {final_reason}")
        return {"allowed": True, "reason": final_reason}
