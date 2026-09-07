"""
Walk-forward validation on REAL SmartAPI data.
Train window: WALK_FORWARD_TRAIN_DAYS (trading days)
Test window: WALK_FORWARD_TEST_DAYS (trading days, untouched)
No parameter optimization grid in v1 — reports baseline params performance on train vs test.
If train looks good and test collapses, print OVERFIT_WARNING.
"""
import sys
import json
import os
import time
import pandas as pd
from datetime import datetime, timedelta
from tabulate import tabulate
from src.config import Config
from src.auth import SmartAPIAuth
from src.instruments import InstrumentManager
from src.historical import HistoricalDataFetcher
from src.strategy import Strategy
from src.backtest import Backtester
from src.metrics import PerformanceMetrics

VALID_INTERVALS = {
    "ONE_MINUTE", "THREE_MINUTE", "FIVE_MINUTE", "TEN_MINUTE", 
    "FIFTEEN_MINUTE", "THIRTY_MINUTE", "ONE_HOUR", "ONE_DAY"
}

def resolve_date_range(interval: str):
    """Resolve from_date and to_date based on interval type."""
    now = datetime.now()
    today = now.date()
    
    if interval == "ONE_DAY":
        # Use config defaults for daily
        from_date = Config.BACKTEST_FROM
        to_date = Config.BACKTEST_TO
        # Validate from_date looks like a date
        if from_date and "-" in from_date and any(c.isdigit() for c in from_date):
            pass  # Use config
        else:
            from_date = "2024-01-01 09:15"
        # Cap to_date to today
        if to_date and "-" in to_date:
            try:
                to_dt = datetime.strptime(to_date.split()[0], "%Y-%m-%d")
                if to_dt.date() > today:
                    to_date = f"{today} 15:30"
            except:
                to_date = f"{today} 15:30"
        else:
            to_date = f"{today} 15:30"
    else:
        # Intraday: default to last 250 calendar days for walk-forward (more history needed)
        from_dt = now - timedelta(days=250)
        from_date = from_dt.strftime("%Y-%m-%d 09:15")
        to_date = now.strftime("%Y-%m-%d 15:30")
    
    return from_date, to_date

def run_walk_forward(symbol: str = "RELIANCE", interval: str = None):
    print("\n========================================================")
    print(f"      WALK-FORWARD VALIDATION: {symbol}")
    print("========================================================\n")

    # Prefer VALIDATION_INTERVAL from config for validation runs
    interval = interval or getattr(Config, "VALIDATION_INTERVAL", "ONE_DAY")

    # 1. Require real SmartAPI credentials
    if not Config.validate_creds():
        print("[ERROR] REAL_DATA_REQUIRED: SmartAPI credentials not configured in .env")
        sys.exit(1)

    print("[1/4] Authenticating with Angel One SmartAPI...")
    auth = SmartAPIAuth()
    smart_api = auth.login()
    time.sleep(2)  # Delay after login to avoid rate limit

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
    
    # Resolve dates based on interval
    from_date, to_date = resolve_date_range(interval)
    
    # Try preferred interval first (FIFTEEN_MINUTE for ORB realism)
    df_data = fetcher.fetch_candles(
        symbol_token=token,
        interval=interval,
        from_date=from_date,
        to_date=to_date
    )
    
    orb_mode = "INTRADAY_15M" if interval == "FIFTEEN_MINUTE" else "DAILY_PROXY"
    
    # Fall back to ONE_DAY if FIFTEEN_MINUTE fails or returns too few bars
    if df_data is None or df_data.empty or len(df_data) < 30:
        print(f"       {interval} fetch failed or insufficient bars. Falling back to ONE_DAY (ORB_MODE=DAILY_PROXY).")
        time.sleep(10)  # Delay before fallback to avoid rate limit
        daily_from, daily_to = resolve_date_range("ONE_DAY")
        df_data = fetcher.fetch_candles(
            symbol_token=token,
            interval="ONE_DAY",
            from_date=daily_from,
            to_date=daily_to
        )
        orb_mode = "DAILY_PROXY"
        from_date = daily_from
        to_date = daily_to
        interval = "ONE_DAY"
    
    if df_data is None or df_data.empty:
        print(f"[ERROR] REAL_DATA_REQUIRED: Failed to fetch historical data for {symbol}")
        print(f"       Interval: {interval}, From: {from_date}, To: {to_date}")
        print(f"       SmartAPI returned empty response. Check API limits or date range.")
        sys.exit(1)

    print(f"       Successfully fetched {len(df_data)} historical candles (ORB_MODE: {orb_mode}).")

    # 4. Split by trading days, not bar count
    df_data["timestamp"] = pd.to_datetime(df_data["timestamp"], errors="coerce")
    unique_days = sorted(df_data["timestamp"].dt.date.unique())
    
    train_days = Config.WALK_FORWARD_TRAIN_DAYS
    test_days = Config.WALK_FORWARD_TEST_DAYS
    
    if len(unique_days) < (train_days + test_days):
        # Use largest possible split if insufficient days
        print(f"[WARNING] WARNING_SHORT_HISTORY: Need {train_days + test_days} trading days, got {len(unique_days)}")
        print(f"       Using 70% train / 30% test split instead.")
        split_idx = int(len(unique_days) * 0.7)
        train_day_list = unique_days[:split_idx]
        test_day_list = unique_days[split_idx:]
    else:
        train_day_list = unique_days[:train_days]
        test_day_list = unique_days[train_days:train_days + test_days]
    
    # Filter bars by trading days
    df_train = df_data[df_data["timestamp"].dt.date.isin(train_day_list)].copy()
    df_test = df_data[df_data["timestamp"].dt.date.isin(test_day_list)].copy()

    print(f"[4/4] Running Walk-Forward Analysis...")
    print(f"       Train window: {len(train_day_list)} trading days ({len(df_train)} bars)")
    print(f"       Test window: {len(test_day_list)} trading days ({len(df_test)} bars, untouched)\n")

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
        ["ORB Mode", orb_mode, orb_mode],
        ["Data Window", f"TRAIN ({len(train_day_list)} days, {len(df_train)} bars)", f"TEST ({len(test_day_list)} days, {len(df_test)} bars)"],
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
        "orb_mode": orb_mode,
        "symbol": symbol,
        "train_trading_days": len(train_day_list),
        "test_trading_days": len(test_day_list),
        "train_bars": len(df_train),
        "test_bars": len(df_test),
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
    interval = None
    if len(sys.argv) > 2:
        arg2 = sys.argv[2].upper()
        if arg2 in VALID_INTERVALS:
            interval = arg2
    run_walk_forward(symbol=symbol, interval=interval)
