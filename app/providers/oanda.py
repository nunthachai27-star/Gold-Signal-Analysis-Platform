from datetime import datetime, timezone
import requests
from app.domain import Candle
from app.providers.base import PriceProvider

GRANULARITY = {
    "W1": "W", "D1": "D", "H4": "H4", "H1": "H1",
    "M30": "M30", "M15": "M15", "M5": "M5", "M1": "M1",
}
HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaProvider(PriceProvider):
    def __init__(self, token: str, env: str = "practice", session=None):
        self.token = token
        self.host = HOSTS[env]
        self.session = session or requests.Session()

    def get_candles(self, symbol: str, timeframe: str, count: int = 250) -> list[Candle]:
        url = f"{self.host}/v3/instruments/{symbol}/candles"
        params = {"granularity": GRANULARITY[timeframe], "count": count, "price": "M"}
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.session.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        return self._parse(symbol, timeframe, resp.json())

    @staticmethod
    def _parse(symbol: str, timeframe: str, data: dict) -> list[Candle]:
        out = []
        for c in data.get("candles", []):
            if not c.get("complete", True):
                continue
            mid = c["mid"]
            ts = datetime.strptime(c["time"][:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc)
            out.append(Candle(
                symbol=symbol, timeframe=timeframe, time=ts,
                open=float(mid["o"]), high=float(mid["h"]),
                low=float(mid["l"]), close=float(mid["c"]),
                volume=float(c.get("volume", 0)),
            ))
        return out
