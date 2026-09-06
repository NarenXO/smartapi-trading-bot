import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
from src.historical import HistoricalDataFetcher
from src.config import Config
from src.market_clock import MarketClock

logger = logging.getLogger(__name__)

class RankingEngine:
    def __init__(self, fetcher: HistoricalDataFetcher):
        self.fetcher = fetcher

    def rank_symbols(self, token_map: Dict[str, str]) -> Dict[str, str]:
        """
        Scans all tokens, calculates 15-day Rate of Change (ROC), 
        and returns only the top Config.TOP_K_STOCKS.
        """
        logger.info(f"RANKING_ENGINE_INITIATED_FOR_{len(token_map)}_SYMBOLS")
        now = MarketClock.now_ist()
        from_dt = (now - timedelta(days=20)).strftime("%Y-%m-%d 09:15")
        to_dt = now.strftime("%Y-%m-%d %H:%M")
        
        momentum_scores = {}

        for symbol, token in token_map.items():
            try:
                df = self.fetcher.fetch_candles(token, "ONE_DAY", from_dt, to_dt)
                if df is not None and len(df) >= 15:
                    current_price = df.iloc[-1]['close']
                    past_price = df.iloc[-15]['close']
                    roc = ((current_price - past_price) / past_price) * 100
                    momentum_scores[symbol] = roc
            except Exception:
                continue

        # Sort descending by ROC
        sorted_symbols = sorted(momentum_scores.items(), key=lambda item: item[1], reverse=True)
        top_symbols = sorted_symbols[:Config.TOP_K_STOCKS]
        
        top_token_map = {sym: token_map[sym] for sym, _ in top_symbols}
        logger.info(f"TOP_{Config.TOP_K_STOCKS}_RANKED_SYMBOLS: {[s for s, _ in top_symbols]}")
        
        return top_token_map
