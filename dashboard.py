import os
import glob
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime

from src.config import Config
from src.market_clock import MarketClock
from src.bot_controller import BotController
from src.auth import SmartAPIAuth
from src.instruments import InstrumentManager
from src.historical import HistoricalDataFetcher
from src.strategy import Strategy

# Streamlit Page Config
st.set_page_config(
    page_title="Angel One AI Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Dark Theme CSS
st.markdown("""
<style>
    .main { background-color: #0E1117; }
    div.metric-container {
        background-color: #1E222D;
        border: 1px solid #2A2E39;
        padding: 12px;
        border-radius: 8px;
    }
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Helper: Fetch recent candles & calculate signals for UI chart
@st.cache_data(ttl=60)
def get_chart_data(symbol: str):
    try:
        auth = SmartAPIAuth()
        smart_api = auth.login()
        if not smart_api:
            return None
        inst_mgr = InstrumentManager()
        token = inst_mgr.get_token(symbol, "NSE")
        if not token:
            return None
        fetcher = HistoricalDataFetcher(smart_api)
        now = MarketClock.now_ist()
        from_dt = (now - pd.Timedelta(days=15)).strftime("%Y-%m-%d 09:15")
        to_dt = now.strftime("%Y-%m-%d %H:%M")
        df = fetcher.fetch_candles(token, interval="ONE_DAY", from_date=from_dt, to_dt=to_dt)
        if df is not None and not df.empty:
            strat = Strategy()
            df = strat.generate_signals(df)
            return df
    except Exception:
        pass
    return None

# Top Title & Market Header
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.title("⚡ Angel One Quantitative Trading Terminal")
with header_col2:
    is_open = MarketClock.is_market_open()
    if is_open:
        st.success("🟢 NSE LIVE MARKET OPEN")
    else:
        st.error(f"🔴 MARKET CLOSED | Opens in {MarketClock.time_to_open()}")

st.caption(f"**Last Sync:** {MarketClock.now_ist().strftime('%Y-%m-%d %H:%M:%S IST')} | **Account:** {Config.CLIENT_CODE or 'DEMO'}")

st.divider()

# Sidebar Setup
st.sidebar.title("🎛️ Command Center")
bot_info = BotController.get_status()
bot_running = bot_info["status"] == "RUNNING"
bot_mode = bot_info["mode"]

if bot_running:
    st.sidebar.success(f"● ENGINE RUNNING ({bot_mode} MODE)")
else:
    st.sidebar.warning("○ ENGINE IDLE")

st.sidebar.subheader("Execution Controls")
c1, c2 = st.sidebar.columns(2)
with c1:
    if st.button("▶ Start Paper", use_container_width=True, disabled=bot_running):
        BotController.clear_kill_switch()
        if BotController.start_bot("PAPER"):
            st.rerun()

with c2:
    if st.button("⏹ Stop Engine", use_container_width=True, disabled=not bot_running):
        BotController.stop_bot()
        st.rerun()

st.sidebar.divider()

if st.sidebar.button("🚨 EMERGENCY KILL SWITCH", type="primary", use_container_width=True):
    BotController.trigger_kill_switch()
    st.sidebar.error("KILL SWITCH ACTIVATED!")
    st.rerun()

if os.path.exists("KILL_SWITCH"):
    st.sidebar.error("⚠️ KILL SWITCH IS ACTIVE")
    if st.sidebar.button("Clear Kill Switch"):
        BotController.clear_kill_switch()
        st.sidebar.success("Kill switch cleared.")
        st.rerun()

# Sidebar Config Summary
st.sidebar.divider()
st.sidebar.markdown("### ⚙️ Risk Parameters")
st.sidebar.text(f"Capital: ₹{Config.DEFAULT_CAPITAL:,.2f}")
st.sidebar.text(f"Max Risk/Trade: {Config.DEFAULT_RISK_PER_TRADE_PCT}%")
st.sidebar.text(f"Daily Loss Cap: {Config.MAX_DAILY_LOSS_PCT}%")
st.sidebar.text(f"Dry Run Mode: {Config.DRY_RUN}")
st.sidebar.text(f"Max Qty/Trade: {Config.MAX_QTY_PER_TRADE}")

# Read Trades Log
log_files = sorted(glob.glob("logs/paper_trades_*.csv"), reverse=True)
df_trades = pd.DataFrame()
if log_files:
    try:
        df_trades = pd.read_csv(log_files[0])
    except Exception:
        df_trades = pd.DataFrame()

net_pnl = df_trades['net_pnl'].replace('', 0).astype(float).sum() if not df_trades.empty and 'net_pnl' in df_trades else 0.0
total_charges = df_trades['charges'].replace('', 0).astype(float).sum() if not df_trades.empty and 'charges' in df_trades else 0.0
win_trades = len(df_trades[df_trades['net_pnl'].replace('', 0).astype(float) > 0]) if not df_trades.empty and 'net_pnl' in df_trades else 0
total_closed = len(df_trades[df_trades['action'] == 'SELL']) if not df_trades.empty else 0
win_rate = (win_trades / total_closed * 100) if total_closed > 0 else 0.0

# KPI Metrics Bar
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Portfolio Value", f"₹{Config.DEFAULT_CAPITAL + net_pnl:,.2f}")
m2.metric("Net Realized PnL", f"₹{net_pnl:,.2f}", delta=f"{net_pnl:,.2f}")
m3.metric("Taxes & Charges", f"₹{total_charges:,.2f}")
m4.metric("Win Rate", f"{win_rate:.1f}%")
m5.metric("Completed Trades", total_closed)

st.divider()

# Interactive Strategy Charts Section
st.subheader("� Live Technical Analysis & Signal Visualization")

selected_symbol = st.selectbox("Select Stock Symbol to Analyze", Config.TARGET_SYMBOLS, index=0)

df_chart = get_chart_data(selected_symbol)

if df_chart is not None and not df_chart.empty:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{selected_symbol} - Price, EMA 9/21 & Trading Signals", "RSI (14) Indicator")
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df_chart['timestamp'],
            open=df_chart['open'],
            high=df_chart['high'],
            low=df_chart['low'],
            close=df_chart['close'],
            name="OHLC"
        ),
        row=1, col=1
    )

    # EMA 9 & EMA 21
    if 'ema_fast' in df_chart:
        fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['ema_fast'], mode='lines', name='EMA 9', line=dict(color='#00F0FF', width=1.5)), row=1, col=1)
    if 'ema_slow' in df_chart:
        fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['ema_slow'], mode='lines', name='EMA 21', line=dict(color='#FF007F', width=1.5)), row=1, col=1)

    # BUY / SELL Signal Markers on Chart
    buys = df_chart[df_chart['signal'] == 1]
    sells = df_chart[df_chart['signal'] == -1]

    if not buys.empty:
        fig.add_trace(
            go.Scatter(
                x=buys['timestamp'], y=buys['low'] * 0.99,
                mode='markers', name='BUY Signal',
                marker=dict(symbol='triangle-up', size=12, color='#00FF7F')
            ),
            row=1, col=1
        )

    if not sells.empty:
        fig.add_trace(
            go.Scatter(
                x=sells['timestamp'], y=sells['high'] * 1.01,
                mode='markers', name='SELL Signal',
                marker=dict(symbol='triangle-down', size=12, color='#FF3B30')
            ),
            row=1, col=1
        )

    # RSI Subplot
    if 'rsi' in df_chart:
        fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['rsi'], mode='lines', name='RSI', line=dict(color='#FFFF00', width=1.5)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=550,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"Connect API to view live interactive charts for {selected_symbol}.")

st.divider()

# Trade Audit Journal
st.subheader("📜 System Audit & Trade Journal")
if not df_trades.empty:
    st.dataframe(df_trades, use_container_width=True, hide_index=True)
else:
    st.info("No trades recorded in today's session yet.")
