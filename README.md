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
