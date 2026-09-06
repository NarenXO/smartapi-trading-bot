import os
import glob
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime
import tailer

from src.config import Config
from src.market_clock import MarketClock
from src.bot_controller import BotController
from src.auth import SmartAPIAuth
from src.instruments import InstrumentManager
from src.historical import HistoricalDataFetcher
from src.strategy import Strategy
from src.metrics import PerformanceMetrics

st.set_page_config(page_title="ANGEL_ONE_QUANT_TERMINAL", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main { background-color: #000000; color: #00FF00; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3, p, div, span, label { font-family: 'Courier New', Courier, monospace !important; color: #E0E0E0; }
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { height: 40px; background-color: #111111; border-radius: 0px; border: 1px solid #333333; }
    .stTabs [aria-selected="true"] { background-color: #333333; color: #00FF00 !important; }
    div[data-testid="stMetricValue"] { color: #00FF00; font-size: 24px; font-weight: bold; }
    .stButton>button { background-color: #111111; color: #FFFFFF; border: 1px solid #444444; border-radius: 0px; }
    .stButton>button:hover { border: 1px solid #00FF00; color: #00FF00; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def get_chart_data(symbol: str):
    try:
        auth = SmartAPIAuth()
        api = auth.login()
        if not api: return None
        token = InstrumentManager().get_token(symbol, "NSE")
        if not token: return None
        now = MarketClock.now_ist()
        df = HistoricalDataFetcher(api).fetch_candles(token, "ONE_DAY", (now - pd.Timedelta(days=15)).strftime("%Y-%m-%d 09:15"), now.strftime("%Y-%m-%d %H:%M"))
        return Strategy().generate_signals(df) if df is not None else None
    except Exception: return None

st.title("QUANTITATIVE_EXECUTION_TERMINAL_V1")
st.text(f"SYSTEM_TIME_IST: {MarketClock.now_ist().strftime('%Y-%m-%d %H:%M:%S')} | MARKET_STATE: {'OPEN' if MarketClock.is_market_open() else 'CLOSED'}")
st.divider()

bot_info = BotController.get_status()
bot_running = bot_info["status"] == "RUNNING"

with st.sidebar:
    st.markdown("### SYSTEM_CONTROL")
    st.text(f"STATE: {bot_info['status']}_{bot_info['mode']}")
    
    if st.button("INITIALIZE_PAPER_EXECUTION", use_container_width=True, disabled=bot_running):
        BotController.clear_kill_switch()
        if BotController.start_bot("PAPER"): st.rerun()
    if st.button("TERMINATE_EXECUTION", use_container_width=True, disabled=not bot_running):
        BotController.stop_bot()
        st.rerun()
    if st.button("HARD_KILL_SWITCH", use_container_width=True):
        BotController.trigger_kill_switch()
        st.rerun()
    if os.path.exists("KILL_SWITCH"):
        st.error("KILL_SWITCH_ACTIVE")
        if st.button("RESET_KILL_SWITCH"):
            BotController.clear_kill_switch()
            st.rerun()

    st.markdown("### SYSTEM_PARAMETERS")
    st.text(f"CAPITAL: {Config.DEFAULT_CAPITAL}")
    st.text(f"RISK_PCT: {Config.DEFAULT_RISK_PER_TRADE_PCT}")
    st.text(f"DRY_RUN: {Config.DRY_RUN}")
    st.text(f"HARD_SL: {Config.STOP_LOSS_PCT}%")
    st.text(f"TRAILING_SL: {Config.TRAILING_SL_PCT}%")
    st.text(f"AUTO_SQUARE_OFF: {Config.AUTO_SQUARE_OFF_HOUR}:{Config.AUTO_SQUARE_OFF_MINUTE}")

log_files = sorted(glob.glob("logs/paper_trades_*.csv"), reverse=True)
df_trades = pd.read_csv(log_files[0]) if log_files else pd.DataFrame()

net_pnl = df_trades['net_pnl'].replace('', 0).astype(float).sum() if not df_trades.empty and 'net_pnl' in df_trades else 0.0
m = PerformanceMetrics.calculate_metrics(df_trades, Config.DEFAULT_CAPITAL)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("AUM", f"{Config.DEFAULT_CAPITAL + net_pnl:.2f}")
c2.metric("REALIZED_PNL", f"{net_pnl:.2f}")
c3.metric("WIN_RATE", f"{m['win_rate_pct']}%")
c4.metric("PROFIT_FACTOR", f"{m['profit_factor']}")
c5.metric("SHARPE_RATIO", f"{m['sharpe_ratio']}")
c6.metric("MAX_DRAWDOWN", f"{m['max_drawdown_pct']}%")

tab1, tab2, tab3 = st.tabs(["[MARKET_DATA]", "[EXECUTION_LEDGER]", "[SYSTEM_LOGS]"])

with tab1:
    from src.universe import NIFTY_50_SYMBOLS
    available_symbols = NIFTY_50_SYMBOLS if Config.UNIVERSE_MODE == "NIFTY50" else Config.TARGET_SYMBOLS
    sym = st.selectbox("SYMBOL_SELECT", available_symbols)
    df_chart = get_chart_data(sym)
    if df_chart is not None:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=df_chart['timestamp'], open=df_chart['open'], high=df_chart['high'], low=df_chart['low'], close=df_chart['close'], name="PRICE"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['ema_fast'], line=dict(color='#00F0FF', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['ema_slow'], line=dict(color='#FF007F', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['rsi'], line=dict(color='#FFFF00', width=1)), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    if not df_trades.empty:
        st.dataframe(df_trades, use_container_width=True)
    else:
        st.text("NO_EXECUTION_DATA_FOUND")

with tab3:
    st.text("TAILING_SYSTEM_STDOUT...")
    st.code("System logs will route here in cloud deployment.", language='bash')
