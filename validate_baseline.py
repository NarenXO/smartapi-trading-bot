"""
One-click validation runner.
Runs walk_forward + live backtest for each symbol in TARGET_SYMBOLS.
Prints summary matrix.
States clearly: NO_EDGE_CLAIMED — numbers only.
"""
import sys
import subprocess
from tabulate import tabulate
from src.config import Config

def main():
    print("\n========================================================")
    print("      BASELINE VALIDATION SUITE")
    print("========================================================")
    print(f"Strategy Mode: {Config.STRATEGY_MODE}")
    print(f"Symbols: {Config.TARGET_SYMBOLS}")
    print("\nNOTE: NO_EDGE_CLAIMED — numbers only for diagnostics.\n")

    results = []

    for symbol in Config.TARGET_SYMBOLS:
        print(f"\n--- Validating {symbol} ---")
        
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
        except Exception as e:
            print(f"  ERROR: {e}")
            backtest_success = False

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
        except Exception as e:
            print(f"  ERROR: {e}")
            walkforward_success = False

        results.append({
            "symbol": symbol,
            "backtest": "PASS" if backtest_success else "FAIL",
            "walk_forward": "PASS" if walkforward_success else "FAIL"
        })

    # Print summary matrix
    print("\n========================================================")
    print("      VALIDATION SUMMARY")
    print("========================================================\n")
    
    table_data = [[r["symbol"], r["backtest"], r["walk_forward"]] for r in results]
    print(tabulate(table_data, headers=["Symbol", "Live Backtest", "Walk-Forward"], tablefmt="grid"))
    
    print("\n========================================================")
    print("NO_EDGE_CLAIMED — numbers only for diagnostics.")
    print("========================================================\n")

if __name__ == "__main__":
    main()
