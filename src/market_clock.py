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
