from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

class MarketClock:
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30

    @staticmethod
    def now_ist() -> datetime:
        return datetime.now(IST)

    @staticmethod
    def is_market_open() -> bool:
        now = MarketClock.now_ist()
        if now.weekday() >= 5:
            return False
            
        # Hardcoded NSE Holidays 2024/2025 (YYYY-MM-DD)
        nse_holidays = [
            "2024-01-26", "2024-03-08", "2024-03-25", "2024-04-11", 
            "2024-04-17", "2024-05-01", "2024-06-17", "2024-07-17", 
            "2024-08-15", "2024-10-02", "2024-11-01", "2024-11-15", 
            "2024-12-25", "2025-01-26", "2025-02-26", "2025-03-14",
            "2025-03-31", "2025-04-10", "2025-04-14", "2025-04-18",
            "2025-05-01", "2025-08-15", "2025-08-27", "2025-10-02",
            "2025-10-21", "2025-11-05", "2025-12-25"
        ]
        if now.strftime("%Y-%m-%d") in nse_holidays:
            return False

        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_open <= now <= market_close

    @staticmethod
    def time_to_open() -> str:
        now = MarketClock.now_ist()
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        if now < market_open:
            delta = market_open - now
        else:
            next_day = market_open + timedelta(days=1)
            if next_day.weekday() == 5:
                next_day += timedelta(days=2)
            elif next_day.weekday() == 6:
                next_day += timedelta(days=1)
            delta = next_day - now
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        mins, _ = divmod(remainder, 60)
        return f"{hours}h {mins}m"
