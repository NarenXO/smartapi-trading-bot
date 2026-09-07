import numpy as np
import pandas as pd
from scipy.stats import linregress
from typing import Dict, Any

class PredictiveEngine:
    """
    EXPERIMENTAL diagnostics only.
    linregress returns slope and r_value — NOT a calibrated probability of profit.
    forecast_prob field is REMOVED to avoid false confidence.
    """

    @staticmethod
    def forecast_trend(close_prices: pd.Series, lookback: int = 20) -> Dict[str, Any]:
        if len(close_prices) < lookback:
            return {
                "slope": 0.0,
                "norm_slope": 0.0,
                "r_squared": 0.0,
                "p_value": 1.0,
                "note": "INSUFFICIENT_DATA",
            }

        y = close_prices.tail(lookback).astype(float).values
        x = np.arange(len(y))
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        r_squared = float(r_value ** 2)
        norm_slope = float((slope / y[-1]) * 100) if y[-1] else 0.0

        return {
            "slope": round(float(slope), 6),
            "norm_slope": round(norm_slope, 6),
            "r_squared": round(r_squared, 4),
            "p_value": round(float(p_value), 6),
            "std_err": round(float(std_err), 6),
            "note": "SLOPE_AND_FIT_ONLY_NOT_A_TRADE_PROBABILITY",
        }
