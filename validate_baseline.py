"""
One-click validation runner.
Runs walk_forward + live backtest for each symbol in TARGET_SYMBOLS.
Prints summary matrix with metrics from saved JSON reports.
States clearly: NO_EDGE_CLAIMED — numbers only.
"""
import sys
import subprocess
import json
import os
from tabulate import tabulate
from src.config import Config

def main():
    print("\n========================================================")
    print("      ORB+VWAP+ADX+VOLUME BASELINE VALIDATION")
    print("========================================================")
    print(f"Strategy Mode: {Config.STRATEGY_MODE}")
    print(f"Symbols: {Config.TARGET_SYMBOLS}")
    print("\nNOTE: NO_EDGE_CLAIMED — numbers only for diagnostics.\n")

    results = []

    for symbol in Config.TARGET_SYMBOLS:
        print(f"\n--- Validating {symbol} ---")
        
        backtest_error = ""
        walkforward_error = ""
        
        # Run live backtest
        print(f"  [1/2] Running live backtest for {symbol}...")
        try:
            result = subprocess.run(
                [sys.executable, "run_live_backtest.py", symbol],
                capture_output=True,
                text=True,
                timeout=120
            )
            backtest_success = result.returncode == 0
            if not backtest_success:
                backtest_error = (result.stderr or result.stdout)[:80]
        except Exception as e:
            print(f"  ERROR: {e}")
            backtest_success = False
            backtest_error = str(e)[:80]

        # Run walk-forward
        print(f"  [2/2] Running walk-forward for {symbol}...")
        try:
            result = subprocess.run(
                [sys.executable, "walk_forward.py", symbol],
                capture_output=True,
                text=True,
                timeout=120
            )
            walkforward_success = result.returncode == 0
            if not walkforward_success:
                walkforward_error = (result.stderr or result.stdout)[:80]
        except Exception as e:
            print(f"  ERROR: {e}")
            walkforward_success = False
            walkforward_error = str(e)[:80]

        # Read JSON reports for metrics
        backtest_path = f"data/backtest_report_{symbol}.json"
        walkforward_path = f"data/walk_forward_{symbol}.json"
        
        backtest_metrics = {}
        if os.path.exists(backtest_path):
            try:
                with open(backtest_path, "r") as f:
                    backtest_metrics = json.load(f)
            except Exception:
                pass
        
        walkforward_metrics = {}
        if os.path.exists(walkforward_path):
            try:
                with open(walkforward_path, "r") as f:
                    walkforward_metrics = json.load(f)
            except Exception:
                pass

        # PASS only if report JSON exists and fetch succeeded
        backtest_pass = backtest_success and os.path.exists(backtest_path)
        walkforward_pass = walkforward_success and os.path.exists(walkforward_path)

        results.append({
            "symbol": symbol,
            "backtest": "PASS" if backtest_pass else f"FAIL ({backtest_error})" if backtest_error else "FAIL",
            "walk_forward": "PASS" if walkforward_pass else f"FAIL ({walkforward_error})" if walkforward_error else "FAIL",
            "net_pnl": backtest_metrics.get("net_pnl", "N/A"),
            "trades": backtest_metrics.get("trades", "N/A"),
            "pf": backtest_metrics.get("profit_factor", "N/A"),
            "pf_train": walkforward_metrics.get("train", {}).get("profit_factor", "N/A"),
            "pf_test": walkforward_metrics.get("test", {}).get("profit_factor", "N/A")
        })

    # Print summary matrix with metrics
    print("\n========================================================")
    print("      VALIDATION SUMMARY")
    print("========================================================\n")
    
    table_data = [
        [
            r["symbol"],
            r["backtest"],
            r["walk_forward"],
            r["net_pnl"],
            r["trades"],
            r["pf"],
            r["pf_train"],
            r["pf_test"]
        ]
        for r in results
    ]
    print(tabulate(table_data, headers=["Symbol", "Live Backtest", "Walk-Forward", "Net PnL", "Trades", "PF", "PF Train", "PF Test"], tablefmt="grid"))
    
    print("\n========================================================")
    print("NO_EDGE_CLAIMED — numbers only for diagnostics.")
    print("========================================================\n")

if __name__ == "__main__":
    main()
