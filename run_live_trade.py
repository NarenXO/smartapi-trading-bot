import time
import signal
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
from src.telegram_bot import TelegramNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

class LiveTradingBot:
    def __init__(self, symbols: list = None, poll_interval: int = 60):
        self.symbols = symbols or Config.TARGET_SYMBOLS
        self.poll_interval = poll_interval
        self.running = False
        self.strategy = Strategy()
        self.risk = RiskManager(initial_capital=Config.DEFAULT_CAPITAL)
        self.logger = TradeLogger()
        self.order_engine = None
        self.token_map = {}
        self.fetcher = None
        self.positions = {}
        self.last_signal_time = {}

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("\nShutdown signal received. Stopping gracefully...")
        TelegramNotifier.send_message("⚠️ <b>Bot Shutting Down</b>")
        self.running = False

    def fetch_with_retry(self, token: str, from_dt: str, to_dt: str):
        """API Retry & Timeout Handling"""
        for attempt in range(3):
            try:
                df = self.fetcher.fetch_candles(symbol_token=token, interval="ONE_MINUTE", from_date=from_dt, to_date=to_dt)
                if df is not None and len(df) >= 30:
                    return df
            except Exception as e:
                logger.warning(f"API fetch failed (Attempt {attempt+1}/3): {e}")
                time.sleep(2)
        return None

    def initialize(self) -> bool:
        if not Config.validate_creds():
            logger.error("SmartAPI credentials missing.")
            return False
        
        auth = SmartAPIAuth()
        smart_api = auth.login()
        if not smart_api: return False

        self.order_engine = OrderEngine(smart_api=smart_api, dry_run=Config.DRY_RUN)
        inst_mgr = InstrumentManager()
        for sym in self.symbols:
            token = inst_mgr.get_token(sym, "NSE")
            if token: self.token_map[sym] = token
        
        if not self.token_map: return False
        self.fetcher = HistoricalDataFetcher(smart_api)
        TelegramNotifier.send_message(f"🚀 <b>Bot Started</b>\nMode: {'DRY RUN' if Config.DRY_RUN else 'LIVE'}\nSymbols: {len(self.token_map)}")
        return True

    def run(self):
        if not self.initialize(): return
        self.running = True

        cycle = 0
        while self.running:
            cycle += 1
            if self.risk.check_kill_switch(): break
            
            if not MarketClock.is_market_open():
                time.sleep(60)
                continue

            for symbol, token in self.token_map.items():
                if not self.risk.can_trade(): break

                now = MarketClock.now_ist()
                df = self.fetch_with_retry(token, now.strftime("%Y-%m-%d 09:15"), now.strftime("%Y-%m-%d %H:%M"))
                
                if df is None:
                    continue # Skip cycle if data is bad

                try:
                    df_signals = self.strategy.generate_signals(df)
                    latest = df_signals.iloc[-1]
                    sig = int(latest['signal'])
                    price = float(latest['close'])
                    rsi = float(latest['rsi']) if latest['rsi'] == latest['rsi'] else 0.0
                    atr = float(latest['atr_pct']) if 'atr_pct' in latest else 0.0
                    timestamp = latest['timestamp']

                    # Duplicate Guard
                    if symbol in self.last_signal_time and self.last_signal_time[symbol] == timestamp:
                        continue

                    reason = f"EMA/RSI (RSI:{rsi:.1f}, ATR:{atr:.2f}%)"

                    # 1. HARD SL/TP INDEPENDENT CHECK
                    if symbol in self.positions:
                        pos = self.positions[symbol]
                        entry = pos["entry"]
                        hard_sl = entry * (1 - Config.STOP_LOSS_PCT / 100)
                        hard_tp = entry * (1 + Config.TAKE_PROFIT_PCT / 100)
                        
                        if price <= hard_sl:
                            sig = -1
                            reason = f"HARD STOP-LOSS (Hit {price} <= {hard_sl:.2f})"
                        elif price >= hard_tp:
                            sig = -1
                            reason = f"TAKE-PROFIT (Hit {price} >= {hard_tp:.2f})"

                    # 2. EXECUTE LOGIC
                    if sig == 1 and symbol not in self.positions:
                        if self.risk.can_open_position(symbol):
                            qty = self.risk.get_safe_qty(price, Config.DEFAULT_CAPITAL)
                            if qty > 0:
                                resp = self.order_engine.place_order(symbol, token, "BUY", qty, price)
                                if resp and resp.get("status"):
                                    self.positions[symbol] = {"qty": qty, "entry": price}
                                    self.risk.record_trade(symbol, is_open=True)
                                    self.logger.log_trade({"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "symbol": symbol, "action": "BUY", "price": price, "qty": qty, "notes": reason})
                                    self.last_signal_time[symbol] = timestamp
                                    TelegramNotifier.send_message(f"🟢 <b>BUY {symbol}</b>\nQty: {qty}\nPrice: ₹{price}\nReason: {reason}")

                    elif sig == -1 and symbol in self.positions:
                        pos = self.positions[symbol]
                        resp = self.order_engine.place_order(symbol, token, "SELL", pos["qty"], price)
                        if resp and resp.get("status"):
                            pnl = (price - pos["entry"]) * pos["qty"]
                            self.risk.record_trade(symbol, pnl=pnl, is_open=False)
                            self.logger.log_trade({"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "symbol": symbol, "action": "SELL", "price": price, "qty": pos["qty"], "net_pnl": round(pnl, 2), "notes": reason})
                            del self.positions[symbol]
                            self.last_signal_time[symbol] = timestamp
                            TelegramNotifier.send_message(f"🔴 <b>SELL {symbol}</b>\nQty: {pos['qty']}\nPrice: ₹{price}\nPnL: ₹{pnl:.2f}\nReason: {reason}")
                            
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")

            time.sleep(self.poll_interval)

if __name__ == "__main__":
    bot = LiveTradingBot(poll_interval=60)
    bot.run()
