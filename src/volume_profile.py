import pandas as pd
import numpy as np

class VolumeProfile:
    @staticmethod
    def calculate_poc(df: pd.DataFrame, bins: int = 50) -> float:
        """
        Calculates the Point of Control (POC) - the price level with the highest traded volume.
        """
        if df is None or df.empty or len(df) < 10:
            return 0.0

        min_price = df['low'].min()
        max_price = df['high'].max()
        if min_price == max_price:
            return min_price

        # Create price bins
        price_bins = np.linspace(min_price, max_price, bins)
        volume_profile = np.zeros(bins - 1)

        # Distribute volume across bins
        for _, row in df.iterrows():
            typical_price = (row['high'] + row['low'] + row['close']) / 3
            # Find which bin the typical price falls into
            bin_idx = np.digitize(typical_price, price_bins) - 1
            bin_idx = max(0, min(bin_idx, bins - 2)) # Constrain to valid indices
            volume_profile[bin_idx] += row['volume']

        # Find the bin with max volume
        poc_idx = np.argmax(volume_profile)
        poc_price = (price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2
        
        return round(float(poc_price), 2)
