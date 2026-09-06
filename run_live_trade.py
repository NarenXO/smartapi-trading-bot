import time
import signal
import logging
import glob
import pandas as pd
from datetime import datetime
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
from src.metrics import PerformanceMetrics
from src.institutional_gate import InstitutionalGate
from src.sector_rotation import SectorRotationEngine
from src.corporate_actions import CorporateActionsFilter

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
        self.eod_sent = False
        self.institutional_gate = None
        self._macro_cycle = 0

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("SHUTDOWN_SIGNAL_RECEIVED")
        TelegramNotifier.send_message("SYSTEM_SHUTDOWN_INITIATED")
        self.running = False

    def check_market_regime(self) -> bool:
        """Market Regime Guard: Verifies Nifty 50 is above 50-period EMA."""
        if not Config.MARKET_REGIME_FILTER:
            return True
        try:
            now = MarketClock.now_ist()
            df_nifty = self.fetcher.fetch_candles(
                symboltoken=Config.NIFTY_TOKEN,
                interval="FIFTEEN_MINUTE",
                from_date=(now - pd.Timedelta(days=5)).strftime("%Y-%m-%d 09:15"),
                to_date=now.strftime("%Y-%m-%d %H:%M"),
                exchange="NSE"
            )
            if df_nifty is not None and len(df_nifty) >= 50:
                df_nifty['ema50'] = df_nifty['close'].ewm(span=50, adjust=False).mean()
                latest_close = df_nifty.iloc[-1]['close']
                latest_ema = df_nifty.iloc[-1]['ema50']
                is_bullish = latest_close >= latest_ema
                if not is_bullish:
                    logger.warning(f"MARKET_REGIME_BEARISH: NIFTY50 ({latest_close:.1f}) < 50EMA ({latest_ema:.1f}). Blocking new Longs.")
                return is_bullish
        except Exception as e:
            logger.error(f"MARKET_REGIME_CHECK_FAILED: {e}")
        return True

    def fetch_with_retry(self, token: str, from_dt: str, to_dt: str):
        for attempt in range(3):
            try:
                df = self.fetcher.fetch_candles(symbol_token=token, interval="ONE_MINUTE", from_date=from_dt, to_date=to_dt)
                if df is not None and len(df) >= 30:
                    return df
            except Exception as e:
                logger.warning(f"API_FETCH_FAILED_ATTEMPT_{attempt+1}: {e}")
                time.sleep(2)
        return None

    def send_eod_summary(self):
        if self.eod_sent: return
        try:
            log_files = sorted(glob.glob("logs/paper_trades_*.csv"), reverse=True)
            df_trades = pd.read_csv(log_files[0]) if log_files else pd.DataFrame()
            m = PerformanceMetrics.calculate_metrics(df_trades, Config.DEFAULT_CAPITAL)
            
            summary = (
                f"EOD PERFORMANCE REPORT\n"
                f"Net PnL: Rs{m['net_pnl']:.2f}\n"
                f"Win Rate: {m['win_rate_pct']}%\n"
                f"Profit Factor: {m['profit_factor']}\n"
                f"Sharpe Ratio: {m['sharpe_ratio']}\n"
                f"Max Drawdown: {m['max_drawdown_pct']}%\n"
                f"Total Trades: {m['total_closed_trades']}"
            )
            TelegramNotifier.send_message(summary)
            self.eod_sent = True
        except Exception as e:
            logger.error(f"EOD_SUMMARY_ERROR: {e}")

    def auto_square_off_check(self, now: datetime) -> bool:
        if now.hour >= Config.AUTO_SQUARE_OFF_HOUR and now.minute >= Config.AUTO_SQUARE_OFF_MINUTE:
            logger.warning("AUTO_SQUARE_OFF_TIME_REACHED")
            for symbol, pos in list(self.positions.items()):
                token = self.token_map[symbol]
                price = pos["max_seen_price"]
                resp = self.order_engine.place_order(symbol, token, "SELL", pos["qty"], 0.0)
                if resp and resp.get("status"):
                    pnl = (price - pos["entry"]) * pos["qty"]
                    self.risk.record_trade(symbol, pnl=pnl, is_open=False)
                    self.logger.log_trade({"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "symbol": symbol, "action": "SELL", "price": price, "qty": pos["qty"], "net_pnl": round(pnl, 2), "notes": "AUTO_SQUARE_OFF"})
            self.positions.clear()
            self.send_eod_summary()
            self.running = False
            return True
        return False

    def initialize(self) -> bool:
        if not Config.validate_creds():
            logger.critical("CREDENTIALS_MISSING")
            return False
        
        auth = SmartAPIAuth()
        smart_api = auth.login()
        if not smart_api: return False

        self.order_engine = OrderEngine(smart_api=smart_api, dry_run=Config.DRY_RUN)
        from src.universe import UniverseScanner
        self.token_map = UniverseScanner().get_target_tokens()
        
        if not self.token_map: return False
        self.fetcher = HistoricalDataFetcher(smart_api)
        
        # Rank universe and filter down to TOP_K_STOCKS
        from src.ranking import RankingEngine
        ranker = RankingEngine(self.fetcher)
        self.token_map = ranker.rank_symbols(self.token_map)

        # Initialize institutional gate
        inst_mgr = InstrumentManager()
        sector_engine = SectorRotationEngine(self.fetcher, inst_mgr)
        try:
            sector_engine.refresh()
        except Exception as e:
            logger.warning(f"SECTOR_REFRESH_FAIL: {e}")
        corp_filter = CorporateActionsFilter()
        self.institutional_gate = InstitutionalGate(sector_engine=sector_engine, corp_filter=corp_filter)
        self.institutional_gate.refresh_macro()

        TelegramNotifier.send_message(
            f"QUANT_SYSTEM_READY\n"
            f"MODE: {'DRY_RUN' if Config.DRY_RUN else 'LIVE'}\n"
            f"SYMBOLS: {len(self.token_map)}\n"
            f"REGIME_GUARD: {Config.MARKET_REGIME_FILTER}\n"
            f"FII_DII: {Config.FII_DII_FILTER}\n"
            f"OPTION_OI: {Config.OPTION_OI_FILTER}\n"
            f"SECTOR_ROT: {Config.SECTOR_ROTATION_FILTER}\n"
            f"CORP_ACTIONS: {Config.CORPORATE_ACTIONS_FILTER}\n"
            f"CAPITAL: {Config.DEFAULT_CAPITAL}"
        )
        return True

    def run(self):
        if not self.initialize(): return
        self.running = True

        while self.running:
            if self.risk.check_kill_switch(): break
            now = MarketClock.now_ist()
            if not MarketClock.is_market_open():
                time.sleep(60)
                continue

            if self.auto_square_off_check(now): break
            regime_ok = self.check_market_regime()

            self._macro_cycle += 1
            if self.institutional_gate and (self._macro_cycle == 1 or self._macro_cycle % 5 == 0):
                self.institutional_gate.refresh_macro()

            for symbol, token in self.token_map.items():
                if not self.risk.can_trade(): break

                df = self.fetch_with_retry(token, now.strftime("%Y-%m-%d 09:15"), now.strftime("%Y-%m-%d %H:%M"))
                if df is None: continue

                try:
                    df_signals = self.strategy.generate_signals(df)
                    latest = df_signals.iloc[-1]
                    sig = int(latest['signal'])
                    price = float(latest['close'])
                    rsi = float(latest['rsi']) if latest['rsi'] == latest['rsi'] else 0.0
                    atr = float(latest['atr']) if 'atr' in latest else 1.0
                    atr_pct = float(latest['atr_pct']) if 'atr_pct' in latest else 0.0
                    timestamp = latest['timestamp']

                    if symbol in self.last_signal_time and self.last_signal_time[symbol] == timestamp:
                        continue

                    reason = f"CONFLUENCE_TRIGGER_RSI_{rsi:.1f}_ATR_{atr_pct:.2f}%"

                    # Trailing & Hard SL/TP Check
                    if symbol in self.positions:
                        pos = self.positions[symbol]
                        entry = pos["entry"]
                        if price > pos["max_seen_price"]:
                            pos["max_seen_price"] = price

                        hard_sl = entry * (1 - Config.STOP_LOSS_PCT / 100)
                        hard_tp = entry * (1 + Config.TAKE_PROFIT_PCT / 100)
                        trailing_sl = pos["max_seen_price"] * (1 - Config.TRAILING_SL_PCT / 100)
                        
                        if price <= hard_sl:
                            sig = -1
                            reason = f"HARD_STOP_LOSS_{price}_LTE_{hard_sl:.2f}"
                        elif price >= hard_tp:
                            sig = -1
                            reason = f"TAKE_PROFIT_{price}_GTE_{hard_tp:.2f}"
                        elif price <= trailing_sl and pos["max_seen_price"] > entry * 1.005:
                            sig = -1
                            reason = f"TRAILING_STOP_LOSS_{price}_LTE_{trailing_sl:.2f}"

                    # Execution Logic
                    if sig == 1 and symbol not in self.positions and regime_ok:
                        gate = self.institutional_gate.allows_long(symbol) if self.institutional_gate else {"allowed": True, "reason": "NO_GATE"}
                        if not gate.get("allowed", True):
                            logger.info(f"LONG_BLOCKED_{symbol}: {gate.get('reason')}")
                            continue
                        reason = f"{reason}|{gate.get('reason', '')}"

                        if self.risk.can_open_position(symbol):
                            qty = self.risk.get_volatility_adjusted_qty(price, atr, Config.DEFAULT_CAPITAL)
                            if qty > 0:
                                resp = self.order_engine.place_order(symbol, token, "BUY", qty, price)
                                if resp and resp.get("status"):
                                    self.positions[symbol] = {"qty": qty, "entry": price, "max_seen_price": price}
                                    self.risk.record_trade(symbol, is_open=True)
                                    self.logger.log_trade({"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "symbol": symbol, "action": "BUY", "price": price, "qty": qty, "notes": reason})
                                    self.last_signal_time[symbol] = timestamp
                                    TelegramNotifier.send_message(f"EXECUTE_BUY\nSYMBOL: {symbol}\nQTY: {qty}\nPRICE: {price}\nREASON: {reason}")

                    elif sig == -1 and symbol in self.positions:
                        pos = self.positions[symbol]
                        resp = self.order_engine.place_order(symbol, token, "SELL", pos["qty"], price)
                        if resp and resp.get("status"):
                            pnl = (price - pos["entry"]) * pos["qty"]
                            self.risk.record_trade(symbol, pnl=pnl, is_open=False)
                            self.logger.log_trade({"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "symbol": symbol, "action": "SELL", "price": price, "qty": pos["qty"], "net_pnl": round(pnl, 2), "notes": reason})
                            del self.positions[symbol]
                            self.last_signal_time[symbol] = timestamp
                            TelegramNotifier.send_message(f"EXECUTE_SELL\nSYMBOL: {symbol}\nQTY: {pos['qty']}\nPRICE: {price}\nPNL: {pnl:.2f}\nREASON: {reason}")
                            
                except Exception as e:
                    logger.error(f"PROCESS_ERROR_{symbol}: {e}")

            time.sleep(self.poll_interval)

if __name__ == "__main__":
    bot = LiveTradingBot(poll_interval=60)
    bot.run()
