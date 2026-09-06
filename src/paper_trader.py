import logging
from datetime import datetime
from typing import Dict
from src.config import Config
from src.backtest import Backtester
from src.trade_logger import TradeLogger

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(self, initial_capital: float = None):
        self.capital = initial_capital or Config.DEFAULT_CAPITAL
        self.initial_capital = self.capital
        self.positions: Dict[str, Dict] = {}
        self.logger = TradeLogger()
        self.cost_calc = Backtester(initial_capital=self.capital)
        self.daily_pnl = 0.0
        self.max_daily_loss = self.capital * (Config.MAX_DAILY_LOSS_PCT / 100)
        self.circuit_breaker_active = False

    def execute_signal(self, symbol: str, signal: int, current_price: float):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.circuit_breaker_active:
            logger.warning(f"CIRCUIT BREAKER ACTIVE - Daily loss limit hit. Ignoring signal for {symbol}")
            return

        # BUY
        if signal == 1 and symbol not in self.positions:
            allocated = self.capital * 0.25
            qty = int(allocated // current_price)
            if qty <= 0:
                logger.warning(f"Insufficient capital to buy {symbol} @ {current_price}")
                return

            self.positions[symbol] = {
                "qty": qty,
                "entry_price": current_price,
                "entry_time": timestamp
            }

            self.logger.log_trade({
                "timestamp": timestamp,
                "symbol": symbol,
                "action": "BUY",
                "price": current_price,
                "qty": qty,
                "gross_pnl": "",
                "charges": "",
                "net_pnl": "",
                "capital_after": round(self.capital, 2),
                "notes": "Paper BUY - EMA/RSI signal"
            })
            logger.info(f"PAPER BUY: {qty} x {symbol} @ Rs{current_price}")

        # SELL
        elif signal == -1 and symbol in self.positions:
            pos = self.positions[symbol]
            qty = pos["qty"]
            entry_price = pos["entry_price"]
            buy_val = qty * entry_price
            sell_val = qty * current_price
            gross_pnl = sell_val - buy_val
            charges = self.cost_calc.calculate_charges(buy_val, sell_val)
            net_pnl = gross_pnl - charges

            self.capital += net_pnl
            self.daily_pnl += net_pnl

            self.logger.log_trade({
                "timestamp": timestamp,
                "symbol": symbol,
                "action": "SELL",
                "price": current_price,
                "qty": qty,
                "gross_pnl": round(gross_pnl, 2),
                "charges": round(charges, 2),
                "net_pnl": round(net_pnl, 2),
                "capital_after": round(self.capital, 2),
                "notes": f"Paper SELL - Entry: {pos['entry_time']}"
            })
            logger.info(f"PAPER SELL: {qty} x {symbol} @ Rs{current_price} | Net PnL: Rs{net_pnl}")

            del self.positions[symbol]

            if self.daily_pnl <= -self.max_daily_loss:
                self.circuit_breaker_active = True
                logger.critical(f"DAILY LOSS CIRCUIT BREAKER TRIGGERED! Loss: Rs{self.daily_pnl}")

    def get_status(self) -> str:
        parts = [
            f"Capital: Rs{self.capital:,.2f}",
            f"Daily PnL: Rs{self.daily_pnl:,.2f}",
            f"Open: {len(self.positions)}",
            f"Breaker: {'ON' if self.circuit_breaker_active else 'OFF'}"
        ]
        for sym, pos in self.positions.items():
            parts.append(f"{sym}:{pos['qty']}@{pos['entry_price']}")
        return " | ".join(parts)
