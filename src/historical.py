import logging
import pandas as pd
from typing import Optional
from SmartApi import SmartConnect

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
        Fetches historical candles from SmartAPI.
        Intervals: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, ONE_DAY
        """
        if not self.smart_api:
            logger.warning("SmartAPI client not connected. Cannot fetch live candles.")
            return None

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
                return df
            else:
                logger.error(f"Candle data fetch failed: {response.get('message', 'No data returned')}")
                return None
        except Exception as e:
            logger.error(f"Error fetching candle data: {str(e)}")
            return None
