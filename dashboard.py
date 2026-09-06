import os
import glob
import pandas as pd
import streamlit as st
from datetime import datetime
from src.config import Config
from src.market_clock import MarketClock
from src.bot_controller import BotController

st.set_page_config(
    page_title="Angel One Trading Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title & Market Banner
st.title("🤖 Angel One AI Trading Assistant")

is_open = MarketClock.is_market_open()
market_status_text = "🟢 NSE MARKET IS OPEN" if is_open else f"🔴 MARKET CLOSED (Opens in {MarketClock.time_to_open()})"
st.caption(f"**Status:** {market_status_text} | **Current Time:** {MarketClock.now_ist().strftime('%d %b %Y, %I:%M:%S %p IST')}")

st.divider()

# Sidebar Setup & Controls
st.sidebar.header("⚙️ Bot Controls & Configuration")

# Status check
bot_info = BotController.get_status()
bot_running = bot_info["status"] == "RUNNING"
bot_mode = bot_info["mode"]

if bot_running:
    st.sidebar.success(f"STATUS: RUNNING ({bot_mode} MODE)")
else:
    st.sidebar.info("STATUS: READY / STOPPED")

st.sidebar.subheader("🕹️ Controls")

col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button("▶️ Start Paper Bot", use_container_width=True, disabled=bot_running):
        BotController.clear_kill_switch()
        if BotController.start_bot("PAPER"):
            st.sidebar.success("Paper Bot Started!")
            st.rerun()

with col_btn2:
    if st.button("⏹️ Stop Bot", use_container_width=True, disabled=not bot_running):
        BotController.stop_bot()
        st.sidebar.warning("Bot Stopped.")
        st.rerun()

st.sidebar.divider()

if st.sidebar.button("🚨 EMERGENCY KILL SWITCH", type="primary", use_container_width=True):
    BotController.trigger_kill_switch()
    st.sidebar.error("KILL SWITCH ACTIVATED! All trading halted.")
    st.rerun()

if os.path.exists("KILL_SWITCH"):
    st.sidebar.error("⚠️ KILL_SWITCH file active.")
    if st.sidebar.button("Clear Kill Switch"):
        BotController.clear_kill_switch()
        st.sidebar.success("Kill switch cleared.")
        st.rerun()

# Configuration Overview in Sidebar
st.sidebar.divider()
st.sidebar.subheader("📋 Account Settings")
st.sidebar.text(f"Client Code: {Config.CLIENT_CODE or 'Not Set'}")
st.sidebar.text(f"Capital: ₹{Config.DEFAULT_CAPITAL:,.2f}")
st.sidebar.text(f"Max Risk/Trade: {Config.DEFAULT_RISK_PER_TRADE_PCT}%")
st.sidebar.text(f"Max Daily Loss: {Config.MAX_DAILY_LOSS_PCT}%")
st.sidebar.text(f"Dry Run Mode: {Config.DRY_RUN}")
st.sidebar.text(f"Target Stocks: {', '.join(Config.TARGET_SYMBOLS)}")

# Main Section: Key Performance Metrics
st.subheader("📊 Performance & Portfolio Overview")

# Find latest trade CSV log
log_files = sorted(glob.glob("logs/paper_trades_*.csv"), reverse=True)
df_trades = pd.DataFrame()

if log_files:
    try:
        df_trades = pd.read_csv(log_files[0])
    except Exception:
        df_trades = pd.DataFrame()

# Calculate Dashboard Stats
total_trades_count = len(df_trades[df_trades['action'] == 'SELL']) if not df_trades.empty else 0
net_pnl = df_trades['net_pnl'].replace('', 0).astype(float).sum() if not df_trades.empty and 'net_pnl' in df_trades else 0.0
total_charges = df_trades['charges'].replace('', 0).astype(float).sum() if not df_trades.empty and 'charges' in df_trades else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Current Capital", f"₹{Config.DEFAULT_CAPITAL + net_pnl:,.2f}")
m2.metric("Total Net PnL", f"₹{net_pnl:,.2f}", delta=f"{net_pnl:,.2f}")
m3.metric("Taxes & Charges Paid", f"₹{total_charges:,.2f}")
m4.metric("Completed Trades", total_trades_count)

st.divider()

# Trade History Section
st.subheader("📜 Live Trade History")
if not df_trades.empty:
    st.dataframe(
        df_trades,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No trades logged yet today. When the bot executes trades during market hours, they will show up here automatically.")

st.divider()

# Instructions Section for Non-Technical Users
with st.expander("ℹ️ How to use this bot (Simple Guide)"):
    st.markdown("""
    1. **Paper Trading (Fake Money):** Click **Start Paper Bot** on the left. The bot will watch stocks during market hours (9:15 AM – 3:30 PM) and test trades without risking real money.
    2. **Real Money Trading:** Ensure credentials in `.env` are verified, set `DRY_RUN=False` in `.env`, and click Start.
    3. **Emergency Stop:** Click the red **EMERGENCY KILL SWITCH** button at any time to immediately freeze trading.
    4. **All decisions are logged:** Check the table above for trade entry prices, exit prices, and exact net profit after taxes.
    """)
