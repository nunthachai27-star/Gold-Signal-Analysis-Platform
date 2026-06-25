from abc import ABC, abstractmethod
from app.domain import SignalDecision


class Analyzer(ABC):
    @abstractmethod
    def analyze(self, snapshot: dict) -> SignalDecision:
        ...
