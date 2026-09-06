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
            result["fii_dii"] = FIIDIIClient.allows_longs(Config.FII_DII_MIN_NET_CRORE)
        if Config.OPTION_OI_FILTER:
            result["option_oi"] = OptionOIAnalyzer.long_bias_ok(buffer_pct=0.20)
        self.last_macro = result
        logger.info(
            f"MACRO_GATE FII_DII={result['fii_dii'].get('reason')} "
            f"OI={result['option_oi'].get('reason')}"
        )
        return result

    def allows_long(self, symbol: str) -> Dict[str, Any]:
        reasons = []
        # Macro gates
        if not self.last_macro:
            self.refresh_macro()
        fii = self.last_macro.get("fii_dii", {"allowed": True, "reason": "NA"})
        oi = self.last_macro.get("option_oi", {"allowed": True, "reason": "NA"})
        if not fii.get("allowed", True):
            return {"allowed": False, "reason": fii.get("reason", "FII_DII_BLOCK")}
        if not oi.get("allowed", True):
            return {"allowed": False, "reason": oi.get("reason", "OPTION_OI_BLOCK")}

        if self.corp_filter is not None:
            c = self.corp_filter.allows_symbol(symbol)
            if not c.get("allowed", True):
                return c
            reasons.append(c.get("reason", ""))

        if self.sector_engine is not None:
            s = self.sector_engine.allows_symbol(symbol)
            if not s.get("allowed", True):
                return s
            reasons.append(s.get("reason", ""))

        return {"allowed": True, "reason": "|".join([r for r in reasons if r]) or "INSTITUTIONAL_GATES_PASS"}
