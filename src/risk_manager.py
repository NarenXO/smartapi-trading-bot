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

    def get_safe_qty(self, price: float, available_capital: float) -> int:
        if price <= 0: return 0
        max_by_capital = int(available_capital * 0.25 // price)
        qty = min(Config.MAX_QTY_PER_TRADE, max_by_capital)
        return max(qty, 0)

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
