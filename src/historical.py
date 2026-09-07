import logging
import time
import pandas as pd
from typing import Optional
from SmartApi import SmartConnect
from src.config import Config
from src.candle_cache import CandleCache

logger = logging.getLogger(__name__)

class HistoricalDataFetcher:
    def __init__(self, smart_api: Optional[SmartConnect]):
        self.smart_api = smart_api

    def fetch_candles(
        self,
        symbol_token: str,
        interval: str = "ONE_DAY",
        from_date: str = "2024-01-01 09:15",
        to_date: str = "2024-06-01 15:30",
        exchange: str = "NSE"
    ) -> Optional[pd.DataFrame]:
        """
        Fetches historical candles from SmartAPI with caching and retry/backoff.
        Intervals: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, ONE_DAY
        """
        # Check cache first
        cached = CandleCache.load(symbol_token, interval, from_date, to_date)
        if cached is not None:
            return cached

        if not self.smart_api:
            logger.warning("SmartAPI client not connected. Cannot fetch live candles.")
            return None

        # Retry with exponential backoff on rate limit
        max_retries = getattr(Config, "API_RETRY_MAX", 5)
        base_sleep = getattr(Config, "API_RETRY_BASE_SLEEP", 5)
        backoff_delays = [base_sleep, 15, 30, 60, 90][:max_retries]

        for attempt, delay in enumerate(backoff_delays):
            try:
                params = {
                    "exchange": exchange,
                    "symboltoken": symbol_token,
                    "interval": interval,
                    "fromdate": from_date,
                    "todate": to_date
                }
                logger.info(f"Fetching {interval} candles for token {symbol_token} from {from_date} to {to_date}")
                response = self.smart_api.getCandleData(params)

                if response and response.get("status") and response.get("data"):
                    raw_candles = response["data"]
                    # Format: [timestamp, open, high, low, close, volume]
                    df = pd.DataFrame(raw_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].apply(pd.to_numeric)
                    df['volume'] = df['volume'].astype(int)
                    # Save to cache
                    CandleCache.save(symbol_token, interval, from_date, to_date, df)
                    return df
                else:
                    # Check for rate limit or empty response
                    msg = response.get("message", "") if response else ""
                    error_text = str(response) if response else "empty response"
                    is_rate_limit = ("rate" in msg.lower() or "exceeding" in msg.lower() or 
                                     "access denied" in msg.lower() or not response or 
                                     (isinstance(response, dict) and not response.get("data")))
                    
                    if is_rate_limit and attempt < len(backoff_delays) - 1:
                        logger.error(f"Rate limit detected (attempt {attempt + 1}/{max_retries}): {msg or error_text}")
                        logger.info(f"Sleeping {delay}s before retry...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Candle data fetch failed: {msg or error_text}")
                        return None
            except Exception as e:
                error_msg = str(e)
                is_rate_limit = ("rate" in error_msg.lower() or "exceeding" in error_msg.lower())
                if is_rate_limit and attempt < len(backoff_delays) - 1:
                    logger.error(f"Rate limit exception (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    logger.info(f"Sleeping {delay}s before retry...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Error fetching candle data: {error_msg}")
                    return None

        logger.error(f"Max retries ({max_retries}) exceeded for {symbol_token} {interval}")
        return None
