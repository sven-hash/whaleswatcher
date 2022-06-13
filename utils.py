import os
from datetime import datetime,timedelta

from dotenv import load_dotenv


class Utils:
    load_dotenv()
    apiBase = os.getenv("API_BASE")
    apiExplorerBase = os.getenv("API_EXPLORER_BASE")
    apiTicker = os.getenv("API_TICKER")
    apiKey = {'X-API-KEY': os.getenv("FULLNODE_API_KEY")}

    @staticmethod
    def timeRange(delta):
        return datetime.date(datetime.now() - timedelta(days=delta, minutes=0, seconds=0)).isoformat()

    @staticmethod
    def timeRangeDays(delta):
        start = (datetime.now() - timedelta(days=delta)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = (datetime.now() - timedelta(days=delta)).replace(hour=23, minute=59, second=59, microsecond=0)
        return start, end

    @staticmethod
    def timeRangeHours(delta):
        return datetime.now() - timedelta(hours=delta)

    @staticmethod
    def humanFormat(num, round_to=2):
        # From https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num = round(num / 1000.0, round_to)
        return '{:.{}f} {}'.format(num, round_to, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])
