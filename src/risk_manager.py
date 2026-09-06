import os
import logging
from datetime import datetime, timedelta
from typing import Dict
from src.config import Config
from src.telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)

class RiskManager:
    KILL_SWITCH_FILE = "KILL_SWITCH"

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.daily_pnl = 0.0
        self.max_daily_loss = initial_capital * (Config.MAX_DAILY_LOSS_PCT / 100)
        self.open_positions = 0
        self.trades_today = 0
        self.consecutive_losses = 0
        self.cooldowns: Dict[str, datetime] = {}
        self.halted = False
        self.halt_reason = ""

    def trigger_halt(self, reason: str):
        self.halted = True
        self.halt_reason = reason
        logger.critical(f"TRADING HALTED: {reason}")
        TelegramNotifier.send_message(f"🚨 <b>TRADING HALTED</b>\nReason: {reason}")

    def check_kill_switch(self) -> bool:
        if os.path.exists(self.KILL_SWITCH_FILE):
            if not self.halted:
                self.trigger_halt("KILL_SWITCH file detected")
            return True
        return False

    def check_daily_loss(self) -> bool:
        if self.daily_pnl <= -self.max_daily_loss:
            self.trigger_halt(f"Daily loss limit hit: Rs{self.daily_pnl:,.2f}")
            return True
        return False

    def check_consecutive_losses(self) -> bool:
        if self.consecutive_losses >= Config.MAX_CONSECUTIVE_LOSSES:
            self.trigger_halt(f"Max consecutive losses ({Config.MAX_CONSECUTIVE_LOSSES}) reached.")
            return True
        return False

    def can_trade(self) -> bool:
        if self.halted: return False
        if self.check_kill_switch(): return False
        if self.check_daily_loss(): return False
        if self.check_consecutive_losses(): return False
        return True

    def can_open_position(self, symbol: str) -> bool:
        if not self.can_trade(): return False
        if self.open_positions >= Config.MAX_OPEN_POSITIONS:
            logger.warning(f"Max positions reached. Blocking {symbol}.")
            return False
        if symbol in self.cooldowns and datetime.now() < self.cooldowns[symbol]:
            logger.warning(f"Cooldown active for {symbol}. Skipping.")
            return False
        return True

    def get_volatility_adjusted_qty(self, price: float, atr: float, total_capital: float) -> int:
        """
        Calculates position size where max loss if stopped out (2 * ATR) equals exactly
        Config.RISK_PER_TRADE_FRACTION (1%) of account equity.
        """
        if price <= 0 or atr <= 0:
            return 1 if Config.MAX_QTY_PER_TRADE == 1 else 0

        risk_amount = total_capital * Config.RISK_PER_TRADE_FRACTION
        risk_per_share = 2.0 * atr  # Stop loss distance = 2x ATR

        qty_by_volatility = int(risk_amount // risk_per_share) if risk_per_share > 0 else 1
        max_capital_qty = int((total_capital * 0.25) // price)

        target_qty = min(qty_by_volatility, max_capital_qty)
        final_qty = min(target_qty, Config.MAX_QTY_PER_TRADE) if Config.MAX_QTY_PER_TRADE > 0 else target_qty
        
        return max(final_qty, 1)

    def record_trade(self, symbol: str, pnl: float = 0.0, is_open: bool = True):
        self.trades_today += 1
        self.daily_pnl += pnl
        if is_open:
            self.open_positions += 1
        else:
            self.open_positions = max(0, self.open_positions - 1)
            if pnl < 0:
                self.consecutive_losses += 1
                self.cooldowns[symbol] = datetime.now() + timedelta(minutes=Config.COOLDOWN_MINUTES)
            else:
                self.consecutive_losses = 0

    def get_status(self) -> str:
        return f"Risk: PnL=Rs{self.daily_pnl:,.2f} | Open={self.open_positions}/{Config.MAX_OPEN_POSITIONS} | ConsecLoss={self.consecutive_losses} | Status={'HALTED' if self.halted else 'ACTIVE'}"
