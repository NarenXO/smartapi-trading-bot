import pandas as pd
import pandas_ta as ta
from src.config import Config

class Strategy:
    def __init__(self, ema_fast: int = 9, ema_slow: int = 21, rsi_period: int = 14, rsi_overbought: int = 70, rsi_oversold: int = 30):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Expects a DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        Returns DataFrame with added indicator columns and 'signal' column (1: BUY, -1: SELL, 0: HOLD)
        """
        data = df.copy()
        
        # Calculate Indicators
        data['ema_fast'] = ta.ema(data['close'], length=self.ema_fast)
        data['ema_slow'] = ta.ema(data['close'], length=self.ema_slow)
        data['rsi'] = ta.rsi(data['close'], length=self.rsi_period)
        # ATR Volatility Filter
        data['atr'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        data['atr_pct'] = (data['atr'] / data['close']) * 100
        
        data['signal'] = 0
        
        # EMA Crossover Conditions
        bullish_cross = (data['ema_fast'] > data['ema_slow']) & (data['ema_fast'].shift(1) <= data['ema_slow'].shift(1))
        bearish_cross = (data['ema_fast'] < data['ema_slow']) & (data['ema_fast'].shift(1) >= data['ema_slow'].shift(1))
        
        # RSI Filters (Avoid buying overbought or selling oversold)
        # Ensure ATR is above minimum threshold to avoid choppy/dead markets
        buy_condition = bullish_cross & (data['rsi'] < self.rsi_overbought) & (data['rsi'] > 40) & (data['atr_pct'] > Config.ATR_MIN_PCT)
        sell_condition = bearish_cross | (data['rsi'] >= self.rsi_overbought)
        
        data.loc[buy_condition, 'signal'] = 1
        data.loc[sell_condition, 'signal'] = -1
        
        return data
