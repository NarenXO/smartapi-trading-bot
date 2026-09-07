import numpy as np
import pandas as pd
from tabulate import tabulate
from src.strategy import Strategy
from src.backtest import Backtester

def generate_mock_ohlcv(days: int = 180) -> pd.DataFrame:
    """Generates synthetic trending & ranging OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=days, freq='D')
    price = 1000.0
    prices = []
    
    for _ in range(days):
        change = np.random.normal(0.5, 15)
        price = max(100.0, price + change)
        high = price + np.random.uniform(2, 10)
        low = price - np.random.uniform(2, 10)
        close = np.random.uniform(low, high)
        volume = int(np.random.uniform(50000, 200000))
        prices.append([price, high, low, close, volume])
        
    df = pd.DataFrame(prices, columns=['open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = dates
    return df

def main():
    print("\n========================================================")
    print("      SYNTHETIC DATA SMOKE TEST ONLY")
    print("========================================================")
    print("\nWARNING: This backtest uses SYNTHETIC data.")
    print("This does NOT validate strategy edge.")
    print("Use: python run_live_backtest.py SYMBOL")
    print("And: python walk_forward.py SYMBOL")
    print("========================================================\n")
    
    df = generate_mock_ohlcv(days=200)
    strategy = Strategy(ema_fast=9, ema_slow=21, rsi_period=14)
    df_signals = strategy.generate_signals(df)
    
    backtester = Backtester(initial_capital=50000.0, max_trade_pct=0.25)
    results = backtester.run(df_signals, symbol="RELIANCE-MOCK")
    
    table_data = [
        ["Initial Capital", f"INR {results['initial_capital']}"],
        ["Final Capital", f"INR {results['final_capital']}"],
        ["Total Net PnL", f"INR {results['total_net_pnl']}"],
        ["Total Charges & Taxes Paid", f"INR {results['total_charges_paid']}"],
        ["ROI (%)", f"{results['roi_pct']}%"],
        ["Total Completed Trades", results['total_trades']],
        ["Winning Trades", results['winning_trades']],
        ["Win Rate (%)", f"{results['win_rate_pct']}%"]
    ]
    
    print(tabulate(table_data, headers=["Metric", "Value"], tablefmt="grid"))
    print("\n[SUCCESS] Backtest engine validated successfully (SYNTHETIC DATA ONLY).\n")

if __name__ == "__main__":
    main()
