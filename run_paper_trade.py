import time
import signal
import sys
import logging
import pandas as pd
from src.config import Config
from src.auth import SmartAPIAuth
from src.instruments import InstrumentManager
from src.historical import HistoricalDataFetcher
from src.strategy import Strategy
from src.paper_trader import PaperTrader
from src.market_clock import MarketClock
from src.scan_status import ScanStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

class PaperTradingBot:
    def __init__(self, symbols: list = None, poll_interval: int = 60):
        self.symbols = symbols or Config.TARGET_SYMBOLS
        self.poll_interval = poll_interval
        self.running = False
        self.strategy = Strategy(ema_fast=9, ema_slow=21, rsi_period=14)
        self.trader = PaperTrader()
        self.smart_api = None
        self.token_map = {}
        self.fetcher = None

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("\nShutdown signal received. Stopping...")
        self.running = False

    def initialize(self) -> bool:
        if not Config.validate_creds():
            logger.error("SmartAPI credentials not configured in .env")
            logger.info("Add ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN, ANGEL_TOTP_SECRET to .env")
            return False

        logger.info("Authenticating with Angel One SmartAPI...")
        auth = SmartAPIAuth()
        self.smart_api = auth.login()
        if not self.smart_api:
            return False

        logger.info("Loading instrument master...")
        inst_mgr = InstrumentManager()
        for sym in self.symbols:
            token = inst_mgr.get_token(sym, "NSE")
            if token:
                self.token_map[sym] = token
                logger.info(f"  {sym} -> Token: {token}")
            else:
                logger.warning(f"  {sym} -> Token NOT FOUND, skipping")

        if not self.token_map:
            logger.error("No valid tokens resolved. Cannot start.")
            return False

        self.fetcher = HistoricalDataFetcher(self.smart_api)
        return True

    def run(self):
        if not self.initialize():
            return

        self.running = True
        logger.info(f"Paper Trading Bot STARTED | Symbols: {list(self.token_map.keys())}")
        logger.info(f"Poll: {self.poll_interval}s | Capital: Rs{self.trader.capital:,.2f}")
        logger.info("Press Ctrl+C to stop.\n")

        cycle = 0
        while self.running:
            cycle += 1

            if not MarketClock.is_market_open():
                if cycle == 1 or cycle % 10 == 0:
                    logger.info(f"Market CLOSED. Opens in {MarketClock.time_to_open()}. Waiting...")
                time.sleep(60)
                continue

            logger.info(f"--- Cycle {cycle} | {MarketClock.now_ist().strftime('%H:%M:%S')} IST ---")

            scan_diagnostics = []

            for symbol, token in self.token_map.items():
                try:
                    now = MarketClock.now_ist()
                    from_dt = now.strftime("%Y-%m-%d 09:15")
                    to_dt = now.strftime("%Y-%m-%d %H:%M")

                    df = self.fetcher.fetch_candles(
                        symbol_token=token,
                        interval="ONE_MINUTE",
                        from_date=from_dt,
                        to_date=to_dt
                    )

                    if df is not None and len(df) >= 30:
                        df_signals = self.strategy.generate_signals(df)
                        latest = df_signals.iloc[-1]
                        current_signal = int(latest['signal'])
                        current_price = float(latest['close'])
                        rsi_val = float(latest['rsi']) if not pd.isna(latest['rsi']) else 0.0
                        signal_reason = latest.get('signal_reason', 'UNKNOWN')
                        confluence_score = float(latest.get('confluence_score', 0) or 0)

                        if current_signal != 0:
                            action = "BUY" if current_signal == 1 else "SELL"
                            logger.info(f"SIGNAL: {action} {symbol} @ Rs{current_price} (RSI: {rsi_val:.1f})")
                            self.trader.execute_signal(symbol, current_signal, current_price)
                        else:
                            logger.info(f"HOLD {symbol} @ Rs{current_price} (RSI: {rsi_val:.1f})")

                        # Add to diagnostics
                        scan_diagnostics.append({
                            "symbol": symbol,
                            "price": current_price,
                            "signal": current_signal,
                            "reason": signal_reason,
                            "score": confluence_score,
                            "blocked_by": ""
                        })
                    else:
                        logger.warning(f"Insufficient data for {symbol} ({len(df) if df is not None else 0} candles)")

                except Exception as e:
                    logger.error(f"Error processing {symbol}: {str(e)}")

            # Write scan status for UI diagnostics
            ScanStatus.write({
                "mode": Config.STRATEGY_MODE,
                "symbols": scan_diagnostics,
                "open_positions": list(self.trader.positions.keys())
            })

            logger.info(f"STATUS: {self.trader.get_status()}\n")
            time.sleep(self.poll_interval)

        logger.info("Paper Trading Bot stopped.")
        logger.info(f"Final: {self.trader.get_status()}")

if __name__ == "__main__":
    bot = PaperTradingBot(poll_interval=60)
    bot.run()
