import os
import logging
from datetime import datetime
from src.config import Config

logger = logging.getLogger(__name__)

class RiskManager:
    KILL_SWITCH_FILE = "KILL_SWITCH"

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.daily_pnl = 0.0
        self.max_daily_loss = initial_capital * (Config.MAX_DAILY_LOSS_PCT / 100)
        self.open_positions = 0
        self.trades_today = 0
        self.halted = False
        self.halt_reason = ""

    def check_kill_switch(self) -> bool:
        """Returns True if trading should STOP."""
        if os.path.exists(self.KILL_SWITCH_FILE):
            self.halted = True
            self.halt_reason = "KILL_SWITCH file detected"
            logger.critical("KILL SWITCH ACTIVATED - All trading halted")
            return True
        return False

    def check_daily_loss(self) -> bool:
        """Returns True if daily loss limit is breached."""
        if self.daily_pnl <= -self.max_daily_loss:
            self.halted = True
            self.halt_reason = f"Daily loss limit hit: Rs{self.daily_pnl:,.2f}"
            logger.critical(f"DAILY LOSS LIMIT: {self.halt_reason}")
            return True
        return False

    def check_max_positions(self) -> bool:
        """Returns True if max open positions reached."""
        if self.open_positions >= Config.MAX_OPEN_POSITIONS:
            logger.warning(f"Max positions ({Config.MAX_OPEN_POSITIONS}) reached. Blocking new BUY.")
            return True
        return False

    def can_trade(self) -> bool:
        """Master check: returns True only if ALL risk checks pass."""
        if self.halted:
            logger.warning(f"Trading HALTED: {self.halt_reason}")
            return False
        if self.check_kill_switch():
            return False
        if self.check_daily_loss():
            return False
        return True

    def can_open_position(self) -> bool:
        """Check if a new BUY is allowed."""
        if not self.can_trade():
            return False
        if self.check_max_positions():
            return False
        return True

    def get_safe_qty(self, price: float, available_capital: float) -> int:
        """Returns order quantity capped by MAX_QTY_PER_TRADE and capital."""
        max_by_capital = int(available_capital * 0.25 // price) if price > 0 else 0
        qty = min(Config.MAX_QTY_PER_TRADE, max_by_capital)
        return max(qty, 0)

    def record_trade(self, pnl: float = 0.0, is_open: bool = True):
        """Update state after a trade."""
        self.trades_today += 1
        self.daily_pnl += pnl
        if is_open:
            self.open_positions += 1
        else:
            self.open_positions = max(0, self.open_positions - 1)

    def get_status(self) -> str:
        return (
            f"Risk: PnL=Rs{self.daily_pnl:,.2f} | "
            f"Limit=-Rs{self.max_daily_loss:,.2f} | "
            f"Open={self.open_positions}/{Config.MAX_OPEN_POSITIONS} | "
            f"Trades={self.trades_today} | "
            f"Status={'HALTED' if self.halted else 'ACTIVE'}"
        )
