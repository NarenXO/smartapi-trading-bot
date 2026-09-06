import numpy as np
import pandas as pd
from typing import Dict, Any

class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(df_trades: pd.DataFrame, initial_capital: float) -> Dict[str, Any]:
        """Calculates institutional performance metrics from trade history."""
        if df_trades is None or df_trades.empty or 'net_pnl' not in df_trades:
            return {
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "total_closed_trades": 0,
                "net_pnl": 0.0
            }

        sell_trades = df_trades[df_trades['action'] == 'SELL'].copy()
        if sell_trades.empty:
            return {
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "total_closed_trades": 0,
                "net_pnl": 0.0
            }

        pnls = sell_trades['net_pnl'].replace('', 0).astype(float).values
        wins = pnls[pnls > 0]
        losses = np.abs(pnls[pnls < 0])

        gross_profit = np.sum(wins) if len(wins) > 0 else 0.0
        gross_loss = np.sum(losses) if len(losses) > 0 else 0.0

        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 0.0)

        # Cumulative PnL & Peak Drawdown
        cum_pnl = np.cumsum(pnls)
        equity_curve = initial_capital + cum_pnl
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak
        max_drawdown_pct = round(float(np.min(drawdown)) * 100, 2) if len(drawdown) > 0 else 0.0

        # Sharpe Ratio (assuming risk-free rate = 0.06 / 252 daily)
        if len(pnls) > 1 and np.std(pnls) > 0:
            sharpe = round(float((np.mean(pnls) / np.std(pnls)) * np.sqrt(252)), 2)
        else:
            sharpe = 0.0

        win_rate = round(float((len(wins) / len(pnls)) * 100), 1) if len(pnls) > 0 else 0.0

        return {
            "sharpe_ratio": sharpe,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_drawdown_pct,
            "win_rate_pct": win_rate,
            "total_closed_trades": len(pnls),
            "net_pnl": round(float(np.sum(pnls)), 2)
        }
