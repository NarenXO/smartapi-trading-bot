import numpy as np
import pandas as pd
from scipy.stats import linregress
from typing import Dict, Any

class PredictiveEngine:
    @staticmethod
    def forecast_trend(close_prices: pd.Series, lookback: int = 20) -> Dict[str, Any]:
        """
        Calculates 5-period ahead linear regression trend slope, r-squared fit,
        and directional probability score (0.0 to 1.0).
        """
        if len(close_prices) < lookback:
            return {"slope": 0.0, "r_squared": 0.0, "forecast_prob": 0.5}

        y = close_prices.tail(lookback).values
        x = np.arange(len(y))

        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        r_squared = r_value ** 2

        # Normalize slope relative to recent price level
        norm_slope = (slope / y[-1]) * 100

        # Calculate directional forecast probability
        if norm_slope > 0:
            forecast_prob = 0.5 + min(0.45, (norm_slope * r_squared * 5))
        else:
            forecast_prob = 0.5 - min(0.45, (abs(norm_slope) * r_squared * 5))

        return {
            "slope": round(float(slope), 4),
            "norm_slope": round(float(norm_slope), 4),
            "r_squared": round(float(r_squared), 4),
            "forecast_prob": round(float(forecast_prob), 4)
        }
