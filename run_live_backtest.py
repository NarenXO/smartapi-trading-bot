import sys
import json
import os
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
        # Intraday: default to last 60 calendar days
        from_dt = now - timedelta(days=60)
        from_date = from_dt.strftime("%Y-%m-%d 09:15")
        to_date = now.strftime("%Y-%m-%d 15:30")
    
    return from_date, to_date

def run_backtest_pipeline(symbol: str = "RELIANCE", from_date: str = None, to_date: str = None, interval: str = None):
    print("\n========================================================")
    print(f"      REAL DATA VALIDATION BACKTEST: {symbol}")
    print("========================================================\n")

    # Parse CLI: argv[2] could be interval or from_date
    # Phase 15: Prefer FIFTEEN_MINUTE for ORB realism
    interval = interval or "FIFTEEN_MINUTE"
    
    # Resolve dates based on interval if not explicitly provided
    if not from_date or not to_date:
        resolved_from, resolved_to = resolve_date_range(interval)
        from_date = from_date or resolved_from
        to_date = to_date or resolved_to

    # 1. Require real SmartAPI credentials - no mock fallback for validation
    if not Config.validate_creds():
        print("[ERROR] REAL_DATA_REQUIRED: SmartAPI credentials not configured in .env")
        print("Add ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN, ANGEL_TOTP_SECRET to .env")
        sys.exit(1)

    print("[1/5] Authenticating with Angel One SmartAPI...")
    auth = SmartAPIAuth()
    smart_api = auth.login()

    if not smart_api:
        print("[ERROR] REAL_DATA_REQUIRED: SmartAPI authentication failed")
        sys.exit(1)

    print("[2/5] Resolving NSE Symbol Token...")
    inst_mgr = InstrumentManager()
    token = inst_mgr.get_token(symbol, exch_seg="NSE")
    
    if not token:
        print(f"[ERROR] Token not found for symbol: {symbol}")
        sys.exit(1)

    print(f"       Found Token for {symbol}: {token}")

    print("[3/5] Fetching Historical Candles...")
    fetcher = HistoricalDataFetcher(smart_api)
    
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
        # Resolve daily dates for fallback
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
    
    if df_data is None or df_data.empty:
        print(f"[ERROR] REAL_DATA_REQUIRED: Failed to fetch historical data for {symbol}")
        print(f"       Interval: {interval}, From: {from_date}, To: {to_date}")
        print(f"       SmartAPI returned empty response. Check API limits or date range.")
        sys.exit(1)

    print(f"       Successfully fetched {len(df_data)} historical candles (ORB_MODE: {orb_mode}).")

    # 4. Run Strategy and Backtest
    print(f"[4/5] Executing Strategy ({Config.STRATEGY_MODE}) & Cost Calculation...")
    strategy = Strategy()
    df_signals = strategy.generate_signals(df_data)

    backtester = Backtester(initial_capital=Config.DEFAULT_CAPITAL, max_trade_pct=0.25)
    results = backtester.run(df_signals, symbol=symbol)

    # 5. Calculate Performance Metrics
    print("[5/5] Calculating Performance Metrics...")
    trades_history = results.get('trades_history', [])
    if trades_history:
        df_trades = pd.DataFrame(trades_history)
        metrics = PerformanceMetrics.calculate_metrics(df_trades, Config.DEFAULT_CAPITAL)
    else:
        metrics = {
            'net_pnl': results['total_net_pnl'],
            'win_rate_pct': results['win_rate_pct'],
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown_pct': 0.0
        }

    table_data = [
        ["Strategy Mode", Config.STRATEGY_MODE],
        ["ORB Mode", orb_mode],
        ["Target Symbol", results['symbol']],
        ["Data Source", "REAL SMARTAPI"],
        ["Date Range", f"{from_date} to {to_date}"],
        ["Candles Analyzed", len(df_data)],
        ["Initial Capital", f"INR {results['initial_capital']}"],
        ["Final Capital", f"INR {results['final_capital']}"],
        ["Total Net PnL", f"INR {results['total_net_pnl']}"],
        ["Total Charges & Taxes Paid", f"INR {results['total_charges_paid']}"],
        ["ROI (%)", f"{results['roi_pct']}%"],
        ["Total Completed Trades", results['total_trades']],
        ["Winning Trades", results['winning_trades']],
        ["Win Rate (%)", f"{results['win_rate_pct']}%"],
        ["Profit Factor", f"{metrics['profit_factor']}"],
        ["Sharpe Ratio", f"{metrics['sharpe_ratio']}"],
        ["Max Drawdown (%)", f"{metrics['max_drawdown_pct']}%"]
    ]

    print(tabulate(table_data, headers=["Metric", "Value"], tablefmt="grid"))
    print("\n[SUCCESS] Real data validation backtest completed.\n")

    # Save JSON report
    os.makedirs("data", exist_ok=True)
    report_path = f"data/backtest_report_{symbol}.json"
    report = {
        "strategy_mode": Config.STRATEGY_MODE,
        "orb_mode": orb_mode,
        "symbol": symbol,
        "from_date": from_date,
        "to_date": to_date,
        "candles": len(df_data),
        "trades": results['total_trades'],
        "net_pnl": results['total_net_pnl'],
        "charges": results['total_charges_paid'],
        "win_rate_pct": results['win_rate_pct'],
        "profit_factor": metrics['profit_factor'],
        "sharpe_ratio": metrics['sharpe_ratio'],
        "max_drawdown_pct": metrics['max_drawdown_pct'],
        "final_capital": results['final_capital']
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to: {report_path}\n")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    
    # Parse CLI: argv[2] could be interval or from_date
    interval = None
    from_date = None
    to_date = None
    
    if len(sys.argv) > 2:
        arg2 = sys.argv[2].upper()
        if arg2 in VALID_INTERVALS:
            interval = arg2
        else:
            from_date = sys.argv[2]
    
    if len(sys.argv) > 3:
        arg3 = sys.argv[3].upper()
        if arg3 in VALID_INTERVALS and interval is None:
            interval = arg3
        else:
            to_date = sys.argv[3]
    
    if len(sys.argv) > 4:
        arg4 = sys.argv[4].upper()
        if arg4 in VALID_INTERVALS and interval is None:
            interval = arg4
        else:
            to_date = sys.argv[4]
    
    run_backtest_pipeline(symbol=symbol, from_date=from_date, to_date=to_date, interval=interval)
