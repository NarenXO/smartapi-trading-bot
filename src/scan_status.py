import os
import json
from datetime import datetime
from typing import Dict, Any, List

class ScanStatus:
    PATH = "data/last_scan_status.json"

    @classmethod
    def write(cls, payload: Dict[str, Any]):
        os.makedirs("data", exist_ok=True)
        payload["updated_at"] = datetime.now().isoformat()
        with open(cls.PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    @classmethod
    def read(cls) -> Dict[str, Any]:
        if not os.path.exists(cls.PATH):
            return {"status": "NO_SCAN_YET", "symbols": []}
        try:
            with open(cls.PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"status": "READ_ERROR", "symbols": []}
