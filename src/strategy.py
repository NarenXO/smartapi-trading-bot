import pandas as pd
import pandas_ta as ta
from src.config import Config

class Strategy:
    """
    BASELINE (default): EMA fast/slow cross + volume confirmation.
    CONFLUENCE (experimental): optional extra factors, OFF unless STRATEGY_MODE=CONFLUENCE.
    Weights are NOT claimed as optimized edge — experimental mode only for A/B tests.
    """

    def __init__(
        self,
        ema_fast: int = None,
        ema_slow: int = None,
        rsi_period: int = None,
    ):
        self.ema_fast = ema_fast or Config.EMA_FAST
        self.ema_slow = ema_slow or Config.EMA_SLOW
        self.rsi_period = rsi_period or Config.RSI_PERIOD

    def calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        return (tp * df["volume"]).cumsum() / df["volume"].cumsum().replace(0, pd.NA)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        if data.empty:
            data["signal"] = []
            data["signal_reason"] = []
            return data

        data["ema_fast"] = ta.ema(data["close"], length=self.ema_fast)
        data["ema_slow"] = ta.ema(data["close"], length=self.ema_slow)
        data["rsi"] = ta.rsi(data["close"], length=self.rsi_period)
        data["atr"] = ta.atr(data["high"], data["low"], data["close"], length=14)
        data["atr_pct"] = (data["atr"] / data["close"]) * 100
        data["vol_sma"] = ta.sma(data["volume"], length=Config.VOLUME_SMA_PERIOD)

        bullish_cross = (data["ema_fast"] > data["ema_slow"]) & (
            data["ema_fast"].shift(1) <= data["ema_slow"].shift(1)
        )
        bearish_cross = (data["ema_fast"] < data["ema_slow"]) & (
            data["ema_fast"].shift(1) >= data["ema_slow"].shift(1)
        )
        volume_ok = data["volume"] > (data["vol_sma"] * Config.VOLUME_MULT)

        data["signal"] = 0
        data["signal_reason"] = "HOLD"
        data["confluence_score"] = 0.0

        mode = Config.STRATEGY_MODE

        if mode == "BASELINE":
            buy = bullish_cross & volume_ok
            sell = bearish_cross
            data.loc[buy, "signal"] = 1
            data.loc[buy, "signal_reason"] = "BASELINE_BUY_EMA_CROSS_AND_VOLUME"
            data.loc[sell, "signal"] = -1
            data.loc[sell, "signal_reason"] = "BASELINE_SELL_EMA_CROSS_DOWN"
            # Score only for UI diagnostics (not a claimed probability)
            data.loc[buy, "confluence_score"] = 1.0
            data.loc[sell, "confluence_score"] = 0.0
            return data

        # EXPERIMENTAL CONFLUENCE — not default; factors optional via flags
        data["vwap"] = self.calculate_vwap(data)
        score = pd.Series(0.0, index=data.index)
        parts = []

        # Core always in experimental mode
        f_ema = (data["ema_fast"] > data["ema_slow"]).astype(float) * 0.40
        f_vol = volume_ok.astype(float) * 0.40
        score = score + f_ema + f_vol
        parts.append("ema")
        parts.append("vol")

        if Config.USE_RSI_FACTOR:
            f_rsi = ((data["rsi"] > 40) & (data["rsi"] < 70)).astype(float) * 0.10
            score = score + f_rsi
        if Config.USE_VWAP_FACTOR:
            f_vwap = (data["close"] > data["vwap"]).astype(float) * 0.10
            score = score + f_vwap
        if Config.USE_POC_FACTOR:
            try:
                from src.volume_profile import VolumeProfile
                poc = VolumeProfile.calculate_poc(data)
                data["poc"] = poc
                score = score + (data["close"] > poc).astype(float) * 0.10
            except Exception:
                pass
        if Config.USE_PREDICTIVE_FACTOR:
            # Experimental slope sign only — NOT a calibrated probability
            try:
                from src.predictive import PredictiveEngine
                probs = []
                for i in range(len(data)):
                    if i < 20:
                        probs.append(0.0)
                    else:
                        out = PredictiveEngine.forecast_trend(data["close"].iloc[: i + 1], lookback=20)
                        # Use slope sign as binary factor only
                        probs.append(1.0 if out.get("norm_slope", 0) > 0 else 0.0)
                data["predictive_slope_sign"] = probs
                score = score + data["predictive_slope_sign"] * 0.10
            except Exception:
                pass

        # Normalize score to 0-1 roughly by clipping
        data["confluence_score"] = score.clip(0, 1.0)
        thr = Config.CONFLUENCE_THRESHOLD
        buy = (data["confluence_score"] >= thr) & volume_ok & (data["ema_fast"] > data["ema_slow"])
        sell = bearish_cross | (data["rsi"] >= 70)
        data.loc[buy, "signal"] = 1
        data.loc[buy, "signal_reason"] = f"EXPERIMENTAL_CONFLUENCE_BUY_score>={thr}"
        data.loc[sell, "signal"] = -1
        data.loc[sell, "signal_reason"] = "EXPERIMENTAL_SELL"
        return data
