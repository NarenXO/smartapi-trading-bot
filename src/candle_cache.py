import os
import json
import time
import hashlib
import logging
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

class CandleCache:
    DIR = "data/candle_cache"

    @classmethod
    def _path(cls, token: str, interval: str, from_date: str, to_date: str) -> str:
        os.makedirs(cls.DIR, exist_ok=True)
        key = f"{token}|{interval}|{from_date}|{to_date}"
        h = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(cls.DIR, f"{token}_{interval}_{h}.csv")

    @classmethod
    def load(cls, token: str, interval: str, from_date: str, to_date: str) -> Optional[pd.DataFrame]:
        path = cls._path(token, interval, from_date, to_date)
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            if len(df) < 5:
                return None
            logger.info(f"CANDLE_CACHE_HIT {path} rows={len(df)}")
            return df
        except Exception as e:
            logger.warning(f"CANDLE_CACHE_READ_FAIL: {e}")
            return None

    @classmethod
    def save(cls, token: str, interval: str, from_date: str, to_date: str, df: pd.DataFrame):
        if df is None or df.empty:
            return
        path = cls._path(token, interval, from_date, to_date)
        try:
            out = df.copy()
            out.to_csv(path, index=False)
            logger.info(f"CANDLE_CACHE_SAVE {path} rows={len(out)}")
        except Exception as e:
            logger.warning(f"CANDLE_CACHE_WRITE_FAIL: {e}")
