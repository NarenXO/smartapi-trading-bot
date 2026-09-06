import pandas as pd
import pandas_ta as ta
from src.config import Config
from src.predictive import PredictiveEngine

class Strategy:
    def __init__(self, ema_fast: int = 9, ema_slow: int = 21, rsi_period: int = 14):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period

    def calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculates Volume Weighted Average Price (VWAP)."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        tp_v = typical_price * df['volume']
        return tp_v.cumsum() / df['volume'].cumsum()

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        # 1. Technical Indicators
        data['ema_fast'] = ta.ema(data['close'], length=self.ema_fast)
        data['ema_slow'] = ta.ema(data['close'], length=self.ema_slow)
        data['rsi'] = ta.rsi(data['close'], length=self.rsi_period)
        data['atr'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        data['atr_pct'] = (data['atr'] / data['close']) * 100
        data['vwap'] = self.calculate_vwap(data)
        data['vol_sma'] = ta.sma(data['volume'], length=20)

        # 2. Factor Checks
        data['factor_ema'] = (data['ema_fast'] > data['ema_slow']).astype(float) * 0.20
        data['factor_rsi'] = ((data['rsi'] > 45) & (data['rsi'] < 65)).astype(float) * 0.15
        data['factor_vwap'] = (data['close'] > data['vwap']).astype(float) * 0.20
        data['factor_vol'] = (data['volume'] > (data['vol_sma'] * 1.5)).astype(float) * 0.25

        # 3. Predictive Forecast Factor Calculation
        forecast_probs = []
        for i in range(len(data)):
            if i < 20:
                forecast_probs.append(0.5)
            else:
                prices = data['close'].iloc[:i+1]
                pred = PredictiveEngine.forecast_trend(prices, lookback=20)
                forecast_probs.append(pred['forecast_prob'])

        data['predictive_prob'] = forecast_probs
        data['factor_predictive'] = (data['predictive_prob'] > 0.65).astype(float) * 0.20

        # Calculate Intraday POC (Point of Control)
        from src.volume_profile import VolumeProfile
        poc = VolumeProfile.calculate_poc(data)
        data['poc'] = poc
        # Factor: Price must be above POC for Long positions (Support established)
        data['factor_poc'] = (data['close'] > data['poc']).astype(float) * 0.15

        # Adjust factor weights to equal 1.00 total
        data['factor_ema'] = (data['ema_fast'] > data['ema_slow']).astype(float) * 0.15
        data['factor_rsi'] = ((data['rsi'] > 45) & (data['rsi'] < 65)).astype(float) * 0.10
        data['factor_vwap'] = (data['close'] > data['vwap']).astype(float) * 0.15
        data['factor_vol'] = (data['volume'] > (data['vol_sma'] * 1.5)).astype(float) * 0.25
        data['factor_predictive'] = (data['predictive_prob'] > 0.65).astype(float) * 0.20

        # 4. Total Confluence Score Calculation (0.00 to 1.00)
        data['confluence_score'] = (
            data['factor_ema'] +
            data['factor_rsi'] +
            data['factor_vwap'] +
            data['factor_vol'] +
            data['factor_predictive'] +
            data['factor_poc']
        )

        # 5. Signal Generation based on Confluence Threshold
        data['signal'] = 0
        buy_condition = (data['confluence_score'] >= Config.CONFLUENCE_THRESHOLD) & (data['atr_pct'] > Config.ATR_MIN_PCT)
        sell_condition = (data['ema_fast'] < data['ema_slow']) | (data['rsi'] >= 70)

        data.loc[buy_condition, 'signal'] = 1
        data.loc[sell_condition, 'signal'] = -1

        return data
