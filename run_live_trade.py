import time
import signal
import sys
import logging
from src.config import Config
from src.auth import SmartAPIAuth
from src.instruments import InstrumentManager
from src.historical import HistoricalDataFetcher
from src.strategy import Strategy
from src.order_engine import OrderEngine
from src.risk_manager import RiskManager
from src.trade_logger import TradeLogger
from src.market_clock import MarketClock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

class LiveTradingBot:
    def __init__(self, symbols: list = None, poll_interval: int = 60):
        self.symbols = symbols or Config.TARGET_SYMBOLS
        self.poll_interval = poll_interval
        self.running = False
        self.strategy = Strategy(ema_fast=9, ema_slow=21, rsi_period=14)
        self.risk = RiskManager(initial_capital=Config.DEFAULT_CAPITAL)
        self.logger = TradeLogger()
        self.order_engine = None
        self.token_map = {}
        self.fetcher = None
        self.positions = {}

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("\nShutdown signal received. Stopping gracefully...")
        self.running = False

    def initialize(self) -> bool:
        if not Config.validate_creds():
            logger.error("SmartAPI credentials not configured in .env")
            return False

        mode = "DRY RUN (safe)" if Config.DRY_RUN else "LIVE REAL ORDERS"
        logger.info(f"=== TRADING MODE: {mode} ===")
        logger.info(f"Max Qty/Trade: {Config.MAX_QTY_PER_TRADE} | Max Positions: {Config.MAX_OPEN_POSITIONS}")

        if not Config.DRY_RUN:
            logger.warning("WARNING: LIVE MODE ACTIVE. Real orders will be placed.")
            logger.warning("Press Ctrl+C within 10 seconds to abort...")
            time.sleep(10)

        logger.info("Authenticating with Angel One SmartAPI...")
        auth = SmartAPIAuth()
        smart_api = auth.login()
        if not smart_api:
            return False

        self.order_engine = OrderEngine(smart_api=smart_api, dry_run=Config.DRY_RUN)

        logger.info("Loading instrument master...")
        inst_mgr = InstrumentManager()
        for sym in self.symbols:
            token = inst_mgr.get_token(sym, "NSE")
            if token:
                self.token_map[sym] = token
                logger.info(f"  {sym} -> Token: {token}")

        if not self.token_map:
            logger.error("No valid tokens resolved.")
            return False

        self.fetcher = HistoricalDataFetcher(smart_api)
        return True

    def run(self):
        if not self.initialize():
            return

        self.running = True
        logger.info(f"Live Trading Bot STARTED | Symbols: {list(self.token_map.keys())}")
        logger.info(f"Poll: {self.poll_interval}s | Capital: Rs{Config.DEFAULT_CAPITAL:,.2f}")
        logger.info("Press Ctrl+C to stop.\n")

        cycle = 0
        while self.running:
            cycle += 1

            if self.risk.check_kill_switch():
                logger.critical("Kill switch active. Bot stopped.")
                break

            if not MarketClock.is_market_open():
                if cycle == 1 or cycle % 10 == 0:
                    logger.info(f"Market CLOSED. Opens in {MarketClock.time_to_open()}.")
                time.sleep(60)
                continue

            logger.info(f"--- Cycle {cycle} | {MarketClock.now_ist().strftime('%H:%M:%S')} IST ---")

            for symbol, token in self.token_map.items():
                if not self.risk.can_trade():
                    break

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
                        sig = int(latest['signal'])
                        price = float(latest['close'])
                        rsi = float(latest['rsi']) if latest['rsi'] == latest['rsi'] else 0.0

                        if sig == 1 and symbol not in self.positions:
                            if self.risk.can_open_position():
                                qty = self.risk.get_safe_qty(price, Config.DEFAULT_CAPITAL)
                                if qty > 0:
                                    sl_price = round(price * 0.98, 1)
                                    resp = self.order_engine.place_order(
                                        symbol=symbol, token=token,
                                        transaction_type="BUY", quantity=qty,
                                        price=price, stop_loss=sl_price
                                    )
                                    if resp and resp.get("status"):
                                        self.positions[symbol] = {"qty": qty, "entry": price}
                                        self.risk.record_trade(is_open=True)
                                        self.logger.log_trade({
                                            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                                            "symbol": symbol, "action": "BUY",
                                            "price": price, "qty": qty,
                                            "notes": f"SL@{sl_price} | RSI:{rsi:.1f}"
                                        })

                        elif sig == -1 and symbol in self.positions:
                            pos = self.positions[symbol]
                            resp = self.order_engine.place_order(
                                symbol=symbol, token=token,
                                transaction_type="SELL", quantity=pos["qty"],
                                price=price
                            )
                            if resp and resp.get("status"):
                                pnl = (price - pos["entry"]) * pos["qty"]
                                self.risk.record_trade(pnl=pnl, is_open=False)
                                self.logger.log_trade({
                                    "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                                    "symbol": symbol, "action": "SELL",
                                    "price": price, "qty": pos["qty"],
                                    "net_pnl": round(pnl, 2),
                                    "notes": f"Entry:{pos['entry']} | RSI:{rsi:.1f}"
                                })
                                del self.positions[symbol]
                        else:
                            logger.info(f"HOLD {symbol} @ Rs{price} (RSI: {rsi:.1f})")

                except Exception as e:
                    logger.error(f"Error processing {symbol}: {str(e)}")

            logger.info(f"STATUS: {self.risk.get_status()}")
            time.sleep(self.poll_interval)

        logger.info("Live Trading Bot stopped.")
        logger.info(f"Final: {self.risk.get_status()}")

if __name__ == "__main__":
    bot = LiveTradingBot(poll_interval=60)
    bot.run()
