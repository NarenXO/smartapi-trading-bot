"""
Walk-forward validation on REAL SmartAPI daily data.
Train window: WALK_FORWARD_TRAIN_DAYS
Test window: WALK_FORWARD_TEST_DAYS (untouched)
No parameter optimization grid in v1 — reports baseline params performance on train vs test.
If train looks good and test collapses, print OVERFIT_WARNING.
"""
import sys
import json
import os
import pandas as pd
from tabulate import tabulate
from src.config import Config
from src.auth import SmartAPIAuth
from src.instruments import InstrumentManager
from src.historical import HistoricalDataFetcher
from src.strategy import Strategy
from src.backtest import Backtester
from src.metrics import PerformanceMetrics

def run_walk_forward(symbol: str = "RELIANCE"):
    print("\n========================================================")
    print(f"      WALK-FORWARD VALIDATION: {symbol}")
    print("========================================================\n")

    # 1. Require real SmartAPI credentials
    if not Config.validate_creds():
        print("[ERROR] REAL_DATA_REQUIRED: SmartAPI credentials not configured in .env")
        sys.exit(1)

    print("[1/4] Authenticating with Angel One SmartAPI...")
    auth = SmartAPIAuth()
    smart_api = auth.login()

    if not smart_api:
        print("[ERROR] REAL_DATA_REQUIRED: SmartAPI authentication failed")
        sys.exit(1)

    print("[2/4] Resolving NSE Symbol Token...")
    inst_mgr = InstrumentManager()
    token = inst_mgr.get_token(symbol, exch_seg="NSE")
    
    if not token:
        print(f"[ERROR] Token not found for symbol: {symbol}")
        sys.exit(1)

    print(f"       Found Token for {symbol}: {token}")

    print("[3/4] Fetching Historical Candles for full range...")
    fetcher = HistoricalDataFetcher(smart_api)
    df_data = fetcher.fetch_candles(
        symbol_token=token,
        interval="ONE_DAY",
        from_date=Config.BACKTEST_FROM,
        to_date=Config.BACKTEST_TO
    )

    if df_data is None or df_data.empty:
        print("[ERROR] REAL_DATA_REQUIRED: Failed to fetch historical data")
        sys.exit(1)

    print(f"       Successfully fetched {len(df_data)} historical candles.")

    # 4. Split into train and test windows
    train_days = Config.WALK_FORWARD_TRAIN_DAYS
    test_days = Config.WALK_FORWARD_TEST_DAYS
    
    if len(df_data) < (train_days + test_days):
        print(f"[ERROR] Insufficient data for walk-forward. Need {train_days + test_days} candles, got {len(df_data)}")
        sys.exit(1)

    df_train = df_data.iloc[:train_days].copy()
    df_test = df_data.iloc[train_days:train_days + test_days].copy()

    print(f"[4/4] Running Walk-Forward Analysis...")
    print(f"       Train window: {len(df_train)} candles")
    print(f"       Test window: {len(df_test)} candles (untouched)\n")

    strategy = Strategy()
    backtester = Backtester(initial_capital=Config.DEFAULT_CAPITAL, max_trade_pct=0.25)

    # Run on train data
    df_train_signals = strategy.generate_signals(df_train)
    results_train = backtester.run(df_train_signals, symbol=f"{symbol}_TRAIN")
    trades_train = results_train.get('trades_history', [])
    if trades_train:
        metrics_train = PerformanceMetrics.calculate_metrics(pd.DataFrame(trades_train), Config.DEFAULT_CAPITAL)
    else:
        metrics_train = {'profit_factor': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown_pct': 0.0}

    # Run on test data
    df_test_signals = strategy.generate_signals(df_test)
    results_test = backtester.run(df_test_signals, symbol=f"{symbol}_TEST")
    trades_test = results_test.get('trades_history', [])
    if trades_test:
        metrics_test = PerformanceMetrics.calculate_metrics(pd.DataFrame(trades_test), Config.DEFAULT_CAPITAL)
    else:
        metrics_test = {'profit_factor': 0.0, 'sharpe_ratio': 0.0, 'max_drawdown_pct': 0.0}

    # Print side-by-side comparison
    table_data = [
        ["Strategy Mode", Config.STRATEGY_MODE, Config.STRATEGY_MODE],
        ["Data Window", f"TRAIN ({len(df_train)} days)", f"TEST ({len(df_test)} days)"],
        ["Net PnL", f"INR {results_train['total_net_pnl']}", f"INR {results_test['total_net_pnl']}"],
        ["Win Rate (%)", f"{results_train['win_rate_pct']}%", f"{results_test['win_rate_pct']}%"],
        ["Profit Factor", f"{metrics_train['profit_factor']}", f"{metrics_test['profit_factor']}"],
        ["Sharpe Ratio", f"{metrics_train['sharpe_ratio']}", f"{metrics_test['sharpe_ratio']}"],
        ["Max Drawdown (%)", f"{metrics_train['max_drawdown_pct']}%", f"{metrics_test['max_drawdown_pct']}%"],
        ["Trades", results_train['total_trades'], results_test['total_trades']]
    ]

    print(tabulate(table_data, headers=["Metric", "Train", "Test"], tablefmt="grid"))

    # Overfitting detection
    print("\nOVERFITTING ANALYSIS:")
    pf_train = metrics_train['profit_factor']
    pf_test = metrics_test['profit_factor']
    sharpe_train = metrics_train['sharpe_ratio']
    sharpe_test = metrics_test['sharpe_ratio']

    if pf_train > 1.2 and pf_test < 0.9:
        print("WARNING: OVERFITTING DETECTED (Profit Factor)")
        print("  Train Profit Factor > 1.2 but Test Profit Factor < 0.9")
    elif sharpe_train > 0.5 and sharpe_test < 0:
        print("WARNING: OVERFITTING DETECTED (Sharpe Ratio)")
        print("  Train Sharpe > 0.5 but Test Sharpe < 0")
    else:
        print("No clear overfitting signal detected.")

    # Save JSON report
    os.makedirs("data", exist_ok=True)
    report_path = f"data/walk_forward_{symbol}.json"
    report = {
        "strategy_mode": Config.STRATEGY_MODE,
        "symbol": symbol,
        "train_days": train_days,
        "test_days": test_days,
        "train": {
            "net_pnl": results_train['total_net_pnl'],
            "win_rate_pct": results_train['win_rate_pct'],
            "profit_factor": metrics_train['profit_factor'],
            "sharpe_ratio": metrics_train['sharpe_ratio'],
            "max_drawdown_pct": metrics_train['max_drawdown_pct'],
            "trades": results_train['total_trades']
        },
        "test": {
            "net_pnl": results_test['total_net_pnl'],
            "win_rate_pct": results_test['win_rate_pct'],
            "profit_factor": metrics_test['profit_factor'],
            "sharpe_ratio": metrics_test['sharpe_ratio'],
            "max_drawdown_pct": metrics_test['max_drawdown_pct'],
            "trades": results_test['total_trades']
        },
        "overfitting_warning": pf_train > 1.2 and pf_test < 0.9 or sharpe_train > 0.5 and sharpe_test < 0
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_path}\n")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    run_walk_forward(symbol=symbol)
