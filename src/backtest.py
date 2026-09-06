import pandas as pd
from typing import Dict, Any
from src.config import Config

class Backtester:
    def __init__(self, initial_capital: float = 50000.0, max_trade_pct: float = 0.2):
        self.initial_capital = initial_capital
        self.max_trade_pct = max_trade_pct

    def calculate_charges(self, buy_val: float, sell_val: float) -> float:
        turnover = buy_val + sell_val
        brokerage = Config.BROKERAGE_PER_ORDER * 2 # Buy + Sell
        stt = sell_val * Config.STT_PCT_INTRADAY
        exchange_turnover = turnover * Config.EXCHANGE_TURNOVER_PCT
        gst = (brokerage + exchange_turnover) * Config.GST_PCT
        stamp_duty = buy_val * Config.STAMP_DUTY_BUY_PCT
        return round(brokerage + stt + exchange_turnover + gst + stamp_duty, 2)

    def run(self, df_signals: pd.DataFrame, symbol: str = "EQUITY") -> Dict[str, Any]:
        capital = self.initial_capital
        position = 0
        buy_price = 0.0
        trades = []
        
        for i in range(len(df_signals)):
            row = df_signals.iloc[i]
            price = row['close']
            signal = row['signal']
            timestamp = row['timestamp']
            
            # BUY
            if signal == 1 and position == 0:
                allocated_funds = capital * self.max_trade_pct
                position = int(allocated_funds // price)
                if position > 0:
                    buy_price = price
                    buy_val = position * buy_price
                    trades.append({
                        'type': 'BUY',
                        'timestamp': timestamp,
                        'price': buy_price,
                        'qty': position,
                        'val': buy_val
                    })

            # SELL
            elif signal == -1 and position > 0:
                sell_price = price
                sell_val = position * sell_price
                buy_val = position * buy_price
                gross_pnl = sell_val - buy_val
                charges = self.calculate_charges(buy_val, sell_val)
                net_pnl = gross_pnl - charges
                capital += net_pnl
                
                trades.append({
                    'type': 'SELL',
                    'timestamp': timestamp,
                    'price': sell_price,
                    'qty': position,
                    'val': sell_val,
                    'gross_pnl': round(gross_pnl, 2),
                    'charges': charges,
                    'net_pnl': round(net_pnl, 2),
                    'capital_after': round(capital, 2)
                })
                position = 0
                buy_price = 0.0

        # Performance summary
        sell_trades = [t for t in trades if t['type'] == 'SELL']
        win_trades = [t for t in sell_trades if t['net_pnl'] > 0]
        total_pnl = round(capital - self.initial_capital, 2)
        total_charges = sum(t['charges'] for t in sell_trades)
        
        return {
            'symbol': symbol,
            'initial_capital': self.initial_capital,
            'final_capital': round(capital, 2),
            'total_net_pnl': total_pnl,
            'total_charges_paid': round(total_charges, 2),
            'roi_pct': round((total_pnl / self.initial_capital) * 100, 2),
            'total_trades': len(sell_trades),
            'winning_trades': len(win_trades),
            'win_rate_pct': round((len(win_trades) / len(sell_trades) * 100), 2) if sell_trades else 0.0,
            'trades_history': trades
        }
