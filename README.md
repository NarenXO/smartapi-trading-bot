# SmartAPI Rule-Based Trading Bot

Automated algorithmic trading system using Angel One SmartAPI with technical momentum filters (EMA 9/21 + RSI) and Indian equity charge modeling.

## 🚀 Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/NarenXO/smartapi-trading-bot.git
   cd smartapi-trading-bot
   ```

2. **Setup virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Update your Angel One API credentials in .env
   ```

4. **Run Backtests:**

   **Synthetic Test Run:**
   ```bash
   python run_backtest.py
   ```

   **Live/Historical Data Run:**
   ```bash
   python run_live_backtest.py RELIANCE
   python run_live_backtest.py TCS
   python run_live_backtest.py HDFCBANK
   ```

5. **Run Paper Trading (Live Market Hours):**
   ```bash
   python run_paper_trade.py
   ```
   The bot will authenticate, poll live 1-minute candles during 9:15–15:30 IST, and simulate trades. All paper trades are logged to logs/paper_trades_YYYYMMDD.csv.

6. **Run Live Trading (Real Orders):**
   ```bash
   # First run in DRY_RUN mode (default - safe, no real orders)
   python run_live_trade.py
   
   # When ready, edit .env and set DRY_RUN=False
   # Then run again for real orders
   python run_live_trade.py
   ```
   Safety Features:
   - DRY_RUN=True (default): Logs orders but places none
   - MAX_QTY_PER_TRADE=1: Starts with 1 share
   - MAX_OPEN_POSITIONS=3: Caps simultaneous positions
   - KILL_SWITCH: Create a file named KILL_SWITCH in project root to halt immediately
   - Daily loss cap: Auto-stops at 3% loss

## Phase 12: Zero-Cost Institutional Intelligence

The bot now includes institutional-grade data layers using free NSE APIs:

- **FII/DII Flow Filter**: Blocks new LONG positions when combined institutional net flow is negative (configurable threshold). Fetches from NSE public API. Fails open if data unavailable.
- **Option Chain OI Walls**: Detects Nifty option chain support/resistance levels (max Put/Call OI). Blocks longs if spot is pinned near call-wall resistance. Fails open if data unavailable.
- **Sector Rotation**: Only allows LONGs in stocks whose sector is among top-ranked sectoral indices by 5-day ROC. Maps Nifty 50 symbols to sector buckets (BANK, IT, AUTO, PHARMA, FMCG, METAL, ENERGY, etc.). Fails open if indices unresolved.
- **Corporate Actions Pause**: Skips symbols with known event dates from `data/corporate_actions.csv`. Pauses from T-1 through T+0. User-editable CSV format: `symbol,event_date,event_type,notes`.

All filters are configurable via environment variables and can be toggled independently. The system uses fail-open behavior when NSE data is blocked (logs warning, does not crash bot).

## 🌐 Easy Web Interface (No Terminal Required)

Double click `Start_App.bat` or run:
```bash
streamlit run dashboard.py
```
This opens a clean browser dashboard at http://localhost:8501 where you can:
- Start & Stop the trading bot with 1 click
- View Live Capital, Profit/Loss, and Brokerage Taxes
- View Live Trade History in a clean visual table
- Trigger an Emergency Kill Switch anytime
