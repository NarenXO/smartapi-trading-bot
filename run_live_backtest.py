import sys
import pandas as pd
from tabulate import tabulate
from src.config import Config
from src.auth import SmartAPIAuth
from src.instruments import InstrumentManager
from src.historical import HistoricalDataFetcher
from src.strategy import Strategy
from src.backtest import Backtester
from run_backtest import generate_mock_ohlcv

def run_backtest_pipeline(symbol: str = "RELIANCE", from_date: str = "2024-01-01 09:15", to_date: str = "2024-06-01 15:30"):
    print("\n========================================================")
    print(f"      ANGEL ONE HISTORICAL BACKTEST: {symbol}")
    print("========================================================\n")

    df_data: pd.DataFrame = None
    is_live_data = False

    # 1. Attempt Live SmartAPI Fetch if credentials configured
    if Config.validate_creds():
        print("[1/4] Authenticating with Angel One SmartAPI...")
        auth = SmartAPIAuth()
        smart_api = auth.login()

        if smart_api:
            print("[2/4] Resolving NSE Symbol Token...")
            inst_mgr = InstrumentManager()
            token = inst_mgr.get_token(symbol, exch_seg="NSE")
            
            if token:
                print(f"       Found Token for {symbol}: {token}")
                print("[3/4] Fetching Historical Candles...")
                fetcher = HistoricalDataFetcher(smart_api)
                df_data = fetcher.fetch_candles(
                    symbol_token=token,
                    interval="ONE_DAY",
                    from_date=from_date,
                    to_date=to_date
                )
                if df_data is not None and not df_data.empty:
                    is_live_data = True
                    print(f"       Successfully fetched {len(df_data)} historical candles.")

    # 2. Fallback to mock data if live data unavailable
    if df_data is None or df_data.empty:
        print("[INFO] Live SmartAPI credentials not present or fetch skipped. Using offline market dataset.")
        df_data = generate_mock_ohlcv(days=180)
        is_live_data = False

    # 3. Run Strategy and Backtest
    print(f"[4/4] Executing Strategy & Cost Calculation (Data Source: {'LIVE SMARTAPI' if is_live_data else 'OFFLINE TEST DATA'})...\n")
    strategy = Strategy(ema_fast=9, ema_slow=21, rsi_period=14)
    df_signals = strategy.generate_signals(df_data)

    backtester = Backtester(initial_capital=Config.DEFAULT_CAPITAL, max_trade_pct=0.25)
    results = backtester.run(df_signals, symbol=symbol)

    table_data = [
        ["Target Symbol", results['symbol']],
        ["Data Source", "LIVE SMARTAPI" if is_live_data else "OFFLINE DATASET"],
        ["Candles Analyzed", len(df_data)],
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
    print("\n[SUCCESS] Backtest pipeline completed successfully.\n")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    run_backtest_pipeline(symbol=symbol)
