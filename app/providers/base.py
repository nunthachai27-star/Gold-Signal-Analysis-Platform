from abc import ABC, abstractmethod
from app.domain import Candle


class PriceProvider(ABC):
    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, count: int = 250) -> list[Candle]:
        ...
