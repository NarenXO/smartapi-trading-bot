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

# Streamlit Page Setup
st.set_page_config(
    page_title="Angel One AI Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Modern UI Styling (TradingView Dark Theme + Inter Font)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    .stApp {
        background-color: #0B0E14;
        color: #C5C7D0;
    }
    
    /* Card Containers */
    div.metric-card {
        background-color: #131722;
        border: 1px solid #2A2E39;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    /* Custom Metric Text */
    .metric-label {
        font-size: 13px;
        color: #787B86;
        font-weight: 500;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #F0F3FA;
    }
    
    .metric-value-green { color: #089981; }
    .metric-value-red { color: #F23645; }
    
    /* Buttons */
    .stButton>button {
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 10px 16px !important;
        transition: all 0.2s ease !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #131722 !important;
        border-right: 1px solid #2A2E39 !important;
    }
</style>
""", unsafe_allow_html=True)

# Robust Non-Blocking Chart Data Fetcher
@st.cache_data(ttl=120, show_spinner=False)
def get_chart_data_cached(symbol: str):
    try:
        auth = SmartAPIAuth()
        api = auth.login()
        if not api:
            return None
        inst_mgr = InstrumentManager()
        token = inst_mgr.get_token(symbol, "NSE")
        if not token:
            return None
        now = MarketClock.now_ist()
        from_dt = (now - pd.Timedelta(days=10)).strftime("%Y-%m-%d 09:15")
        to_dt = now.strftime("%Y-%m-%d %H:%M")
        
        fetcher = HistoricalDataFetcher(api)
        df = fetcher.fetch_candles(token, "ONE_DAY", from_dt, to_dt)
        if df is not None and not df.empty and len(df) >= 5:
            strat = Strategy()
            return strat.generate_signals(df)
    except Exception:
        pass
    return None

# Top Navigation Bar & Header
header_col1, header_col2 = st.columns([3, 1])

with header_col1:
    st.title("📈 Angel One AI Algorithmic Terminal")
    st.caption(f"Connected Client ID: **{Config.CLIENT_CODE or 'Demo Account'}** | System Time: **{MarketClock.now_ist().strftime('%d %b %Y, %I:%M:%S %p IST')}**")

with header_col2:
    is_open = MarketClock.is_market_open()
    if is_open:
        st.success("🟢 NSE Market Open")
    else:
        st.error(f"🔴 Market Closed (Opens in {MarketClock.time_to_open()})")

st.divider()

# Sidebar: Simple English Controls
st.sidebar.header("🕹️ Bot Controls")

bot_info = BotController.get_status()
bot_running = bot_info["status"] == "RUNNING"
bot_mode = bot_info["mode"]

if bot_running:
    st.sidebar.success(f"Status: Bot Active ({bot_mode} Mode)")
else:
    st.sidebar.info("Status: Bot Idle / Ready")

col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button("▶️ Start Paper Bot", use_container_width=True, disabled=bot_running):
        BotController.clear_kill_switch()
        if BotController.start_bot("PAPER"):
            st.rerun()

with col_btn2:
    if st.button("⏹️ Stop Bot", use_container_width=True, disabled=not bot_running):
        BotController.stop_bot()
        st.rerun()

st.sidebar.divider()

if st.sidebar.button("🚨 Emergency Stop (Kill Switch)", type="primary", use_container_width=True):
    BotController.trigger_kill_switch()
    st.sidebar.error("Emergency Stop Activated! All trading frozen.")
    st.rerun()

if os.path.exists("KILL_SWITCH"):
    st.sidebar.error("⚠️ Emergency Stop file active.")
    if st.sidebar.button("Reset Emergency Stop"):
        BotController.clear_kill_switch()
        st.sidebar.success("Emergency Stop cleared.")
        st.rerun()

# Sidebar Settings Overview
st.sidebar.divider()
st.sidebar.header("⚙️ Risk Parameters")
st.sidebar.text(f"Starting Capital: ₹{Config.DEFAULT_CAPITAL:,.2f}")
st.sidebar.text(f"Risk Per Trade: {Config.DEFAULT_RISK_PER_TRADE_PCT}%")
st.sidebar.text(f"Hard Stop-Loss: {Config.STOP_LOSS_PCT}%")
st.sidebar.text(f"Trailing Stop-Loss: {Config.TRAILING_SL_PCT}%")
st.sidebar.text(f"Auto-Square Off: {Config.AUTO_SQUARE_OFF_HOUR}:{Config.AUTO_SQUARE_OFF_MINUTE:02d} IST")
st.sidebar.text(f"Safety Dry Run: {'ENABLED' if Config.DRY_RUN else 'DISABLED'}")

# Read Trade Data
log_files = sorted(glob.glob("logs/paper_trades_*.csv"), reverse=True)
df_trades = pd.DataFrame()
if log_files:
    try:
        df_trades = pd.read_csv(log_files[0])
    except Exception:
        df_trades = pd.DataFrame()

from src.metrics import PerformanceMetrics
m = PerformanceMetrics.calculate_metrics(df_trades, Config.DEFAULT_CAPITAL)

net_pnl = m['net_pnl']
total_balance = Config.DEFAULT_CAPITAL + net_pnl

# Top Key Performance Indicators (Cards)
m1, m2, m3, m4, m5, m6 = st.columns(6)

m1.metric("Total Balance", f"₹{total_balance:,.2f}")
m2.metric("Today's Profit / Loss", f"₹{net_pnl:,.2f}", delta=f"{net_pnl:,.2f}")
m3.metric("Win Rate", f"{m['win_rate_pct']}%")
m4.metric("Profit Factor", f"{m['profit_factor']}")
m5.metric("Sharpe Ratio", f"{m['sharpe_ratio']}")
m6.metric("Max Drawdown", f"{m['max_drawdown_pct']}%")

st.divider()

# Main Interface Tabs
tab_charts, tab_ledger, tab_logs, tab_scan = st.tabs(["📊 Interactive Stock Charts", "📜 Executed Trades Journal", "🖥️ System Activity Logs", "🔍 Scanner Status"])

with tab_charts:
    st.subheader("Technical Analysis & Algorithm Signals")
    
    from src.universe import NIFTY_50_SYMBOLS
    available_symbols = NIFTY_50_SYMBOLS if Config.UNIVERSE_MODE == "NIFTY50" else Config.TARGET_SYMBOLS
    
    selected_symbol = st.selectbox("Select Stock to Inspect:", available_symbols, index=0)
    
    with st.spinner(f"Loading live chart for {selected_symbol}..."):
        df_chart = get_chart_data_cached(selected_symbol)
    
    if df_chart is not None and not df_chart.empty:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.7, 0.3],
            subplot_titles=(f"{selected_symbol} - Price, EMA 9/21 & Trading Signals", "RSI (14) Momentum Indicator")
        )
        
        # OHLC Candlestick
        fig.add_trace(
            go.Candlestick(
                x=df_chart['timestamp'],
                open=df_chart['open'],
                high=df_chart['high'],
                low=df_chart['low'],
                close=df_chart['close'],
                name="Price"
            ),
            row=1, col=1
        )
        
        # EMA Lines
        if 'ema_fast' in df_chart:
            fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['ema_fast'], mode='lines', name='EMA 9 (Fast)', line=dict(color='#2962FF', width=1.5)), row=1, col=1)
        if 'ema_slow' in df_chart:
            fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['ema_slow'], mode='lines', name='EMA 21 (Slow)', line=dict(color='#FF6D00', width=1.5)), row=1, col=1)
            
        # BUY / SELL Signal Markers
        buys = df_chart[df_chart['signal'] == 1]
        sells = df_chart[df_chart['signal'] == -1]
        
        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=buys['timestamp'], y=buys['low'] * 0.99,
                    mode='markers', name='BUY Signal',
                    marker=dict(symbol='triangle-up', size=14, color='#089981')
                ),
                row=1, col=1
            )
            
        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells['timestamp'], y=sells['high'] * 1.01,
                    mode='markers', name='SELL Signal',
                    marker=dict(symbol='triangle-down', size=14, color='#F23645')
                ),
                row=1, col=1
            )
            
        # RSI Indicator
        if 'rsi' in df_chart:
            fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['rsi'], mode='lines', name='RSI', line=dict(color='#B2B5BE', width=1.5)), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#F23645", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#089981", row=2, col=1)

        fig.update_layout(
            template="plotly_dark",
            height=580,
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis_rangeslider_visible=False,
            showlegend=True,
            paper_bgcolor="#0B0E14",
            plot_bgcolor="#131722"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"Chart data for {selected_symbol} is loading or market data is currently quiet.")

with tab_ledger:
    st.subheader("Executed Trade History")
    if not df_trades.empty:
        st.dataframe(df_trades, use_container_width=True, hide_index=True)
    else:
        st.info("No trades executed yet today. Active trades will appear here automatically.")

with tab_logs:
    st.subheader("Real-Time System Log Feed")
    log_candidates = sorted(glob.glob("logs/*.csv"), reverse=True)
    if log_candidates:
        try:
            with open(log_candidates[0], "r", encoding="utf-8") as f:
                lines = f.readlines()[-50:]
            st.code("".join(lines) if lines else "Log file is empty.", language="text")
        except Exception as e:
            st.error(f"Error reading log file: {e}")
    else:
        st.info("No system log files found for today.")

with tab_scan:
    st.subheader("Scanner Status (Why No Trade)")
    from src.scan_status import ScanStatus
    scan_data = ScanStatus.read()
    
    st.caption(f"Strategy Mode: **{scan_data.get('mode', 'UNKNOWN')}**")
    st.caption(f"Last Updated: **{scan_data.get('updated_at', 'NEVER')}**")
    st.caption(f"Open Positions: **{', '.join(scan_data.get('open_positions', [])) or 'None'}**")
    
    st.info("No trade does not mean the bot is stuck. It means filters did not pass.")
    
    symbols = scan_data.get('symbols', [])
    if symbols:
        st.subheader("Last Scanned Symbols")
        df_scan = pd.DataFrame(symbols)
        st.dataframe(df_scan, use_container_width=True, hide_index=True)
    else:
        st.info("No scan data available yet. Bot may not be running.")

