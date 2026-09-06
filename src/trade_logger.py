import os
import csv
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TradeLogger:
    LOG_DIR = "logs"

    def __init__(self):
        os.makedirs(self.LOG_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        self.filepath = os.path.join(self.LOG_DIR, f"paper_trades_{today}.csv")
        self._ensure_header()

    def _ensure_header(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "symbol", "action", "price", "qty",
                    "gross_pnl", "charges", "net_pnl", "capital_after", "notes"
                ])

    def log_trade(self, trade: Dict[str, Any]):
        with open(self.filepath, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.get("timestamp", ""),
                trade.get("symbol", ""),
                trade.get("action", ""),
                trade.get("price", ""),
                trade.get("qty", ""),
                trade.get("gross_pnl", ""),
                trade.get("charges", ""),
                trade.get("net_pnl", ""),
                trade.get("capital_after", ""),
                trade.get("notes", "")
            ])
        logger.info(f"Trade logged: {trade.get('action')} {trade.get('symbol')} @ {trade.get('price')}")
