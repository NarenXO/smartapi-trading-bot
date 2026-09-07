import pandas as pd
import pandas_ta as ta
import numpy as np
from src.config import Config

class Strategy:
    """
    BASELINE (Phase 15): Opening Range Breakout + VWAP + ADX + Volume.
    Conditions for BUY (all required):
      1) Price breaks above first ORB_MINUTES range high (session/day opening range)
      2) Close >= VWAP (if ORB_REQUIRE_ABOVE_VWAP)
      3) ADX >= ADX_MIN
      4) Volume > VOLUME_MULT * volume SMA
    SELL:
      - Close breaks back below opening range high (failed breakout), OR
      - Close below VWAP after being in position signal context, OR
      - ADX collapse optional not used; keep simple: bearish cross of range mid / below ORB low
    For DAILY bars backtests: opening range approximated as prior day high/low breakout
      with same ADX+volume+VWAP filters (documented in signal_reason).
    CONFLUENCE mode: leave minimal experimental stub without fake probabilities.
    """

    def __init__(self, ema_fast: int = None, ema_slow: int = None, rsi_period: int = None):
        self.ema_fast = ema_fast or getattr(Config, "EMA_FAST", 9)
        self.ema_slow = ema_slow or getattr(Config, "EMA_SLOW", 21)
        self.rsi_period = rsi_period or getattr(Config, "RSI_PERIOD", 14)

    def calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        tp = (df["high"] + df["low"] + df["close"]) / 3.0
        cum_vol = df["volume"].cumsum().replace(0, np.nan)
        return (tp * df["volume"]).cumsum() / cum_vol

    def _ensure_datetime(self, data: pd.DataFrame) -> pd.DataFrame:
        d = data.copy()
        if "timestamp" not in d.columns:
            d["timestamp"] = pd.RangeIndex(len(d))
        d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
        return d

    def _compute_intraday_orb(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Build session opening range from first ORB_MINUTES minutes per calendar day.
        Expects intraday timestamps. If bars are daily (date-only / one bar per day),
        falls back to daily proxy.
        """
        d = data.copy()
        d["date"] = d["timestamp"].dt.date
        # Detect intraday: multiple bars per day
        counts = d.groupby("date")["timestamp"].transform("count")
        is_intraday = bool((counts > 1).any())

        orb_high = pd.Series(np.nan, index=d.index)
        orb_low = pd.Series(np.nan, index=d.index)
        orb_ready = pd.Series(False, index=d.index)

        if is_intraday:
            minutes = int(Config.ORB_MINUTES)
            for day, idx in d.groupby("date").groups.items():
                day_df = d.loc[idx].sort_values("timestamp")
                if day_df.empty:
                    continue
                t0 = day_df["timestamp"].iloc[0]
                # Opening window end
                t_end = t0 + pd.Timedelta(minutes=minutes)
                window = day_df[day_df["timestamp"] <= t_end]
                if window.empty:
                    window = day_df.iloc[:1]
                oh = float(window["high"].max())
                ol = float(window["low"].min())
                # After window ends, ORB is known
                after = day_df["timestamp"] > t_end
                # Also mark last window bar as ready for next bars
                orb_high.loc[day_df.index] = oh
                orb_low.loc[day_df.index] = ol
                orb_ready.loc[day_df.index[after]] = True
                # If no bar strictly after (short day), no breakout signals that day
        else:
            # DAILY PROXY for historical ONE_DAY backtests:
            # Use prior day's high/low as the "opening range" to break.
            d_sorted = d.sort_values("timestamp")
            prev_high = d_sorted["high"].shift(1)
            prev_low = d_sorted["low"].shift(1)
            orb_high = prev_high.reindex(d.index)
            orb_low = prev_low.reindex(d.index)
            orb_ready = orb_high.notna()

        d["orb_high"] = orb_high
        d["orb_low"] = orb_low
        d["orb_ready"] = orb_ready.fillna(False)
        d["is_intraday_orb"] = is_intraday
        return d

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            out = df.copy() if df is not None else pd.DataFrame()
            out["signal"] = []
            out["signal_reason"] = []
            out["confluence_score"] = []
            return out

        data = self._ensure_datetime(df)
        data = self._compute_intraday_orb(data)

        # Indicators
        data["vwap"] = self.calculate_vwap(data)
        data["vol_sma"] = ta.sma(data["volume"], length=int(Config.VOLUME_SMA_PERIOD))
        adx_df = ta.adx(data["high"], data["low"], data["close"], length=int(Config.ADX_PERIOD))
        # pandas_ta ADX columns typically ADX_{period}
        adx_col = None
        if adx_df is not None:
            for c in adx_df.columns:
                if str(c).startswith("ADX"):
                    adx_col = c
                    break
            if adx_col is not None:
                data["adx"] = adx_df[adx_col]
            else:
                data["adx"] = np.nan
        else:
            data["adx"] = np.nan

        data["atr"] = ta.atr(data["high"], data["low"], data["close"], length=14)
        data["atr_pct"] = (data["atr"] / data["close"]) * 100
        data["ema_fast"] = ta.ema(data["close"], length=self.ema_fast)
        data["ema_slow"] = ta.ema(data["close"], length=self.ema_slow)
        data["rsi"] = ta.rsi(data["close"], length=self.rsi_period)

        volume_ok = data["volume"] > (data["vol_sma"] * float(Config.VOLUME_MULT))
        adx_ok = data["adx"] >= float(Config.ADX_MIN)
        vwap_ok = data["close"] >= data["vwap"] if Config.ORB_REQUIRE_ABOVE_VWAP else pd.Series(True, index=data.index)

        # Breakout: close crosses above orb_high after range is ready
        above = data["close"] > data["orb_high"]
        crossed = above & (~above.shift(1).fillna(False)) & data["orb_ready"]

        data["signal"] = 0
        data["signal_reason"] = "HOLD"
        data["confluence_score"] = 0.0

        mode = str(getattr(Config, "STRATEGY_MODE", "BASELINE")).upper()

        if mode == "BASELINE":
            buy = crossed & vwap_ok & adx_ok & volume_ok & data["orb_high"].notna()
            # Exit: close back below orb_high (failed breakout) or below orb_low
            failed = data["orb_ready"] & data["orb_high"].notna() & (data["close"] < data["orb_high"]) & (data["close"].shift(1) >= data["orb_high"])
            panic = data["orb_ready"] & data["orb_low"].notna() & (data["close"] < data["orb_low"])

            data.loc[buy, "signal"] = 1
            data.loc[buy, "confluence_score"] = 1.0
            # reason distinguishes intraday ORB vs daily proxy
            for i in data.index[buy]:
                kind = "INTRADAY_ORB" if bool(data.at[i, "is_intraday_orb"]) else "DAILY_PROXY_PRIOR_HIGH"
                data.at[i, "signal_reason"] = (
                    f"BASELINE_BUY_{kind}_VWAP_ADX{Config.ADX_MIN}_VOL"
                )

            sell = failed | panic
            data.loc[sell, "signal"] = -1
            data.loc[sell, "signal_reason"] = "BASELINE_SELL_FAILED_BREAKOUT_OR_BELOW_ORB_LOW"
            data.loc[sell, "confluence_score"] = 0.0
            return data

        # EXPERIMENTAL legacy stub (not default)
        bullish = (data["ema_fast"] > data["ema_slow"]) & volume_ok
        bearish = data["ema_fast"] < data["ema_slow"]
        data.loc[bullish, "signal"] = 1
        data.loc[bullish, "signal_reason"] = "EXPERIMENTAL_CONFLUENCE_EMA_VOL"
        data.loc[bearish, "signal"] = -1
        data.loc[bearish, "signal_reason"] = "EXPERIMENTAL_SELL"
        return data
