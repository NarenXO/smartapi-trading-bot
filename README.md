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
