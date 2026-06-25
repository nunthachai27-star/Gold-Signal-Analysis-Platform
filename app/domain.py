from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    symbol: str
    timeframe: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class TimeframeIndicators:
    timeframe: str
    close: float
    ema_fast: float
    ema_slow: float
    rsi: float
    macd: float
    macd_signal: float
    atr: float
    swing_high: float
    swing_low: float
    trend: str  # "up" | "down" | "side"


@dataclass
class SignalDecision:
    direction: str  # "BUY" | "SELL" | "NONE"
    entry: float
    sl: float
    tp1: float
    tp2: float
    buy_prob: float
    sell_prob: float
    type: str  # "Scalp" | "Normal"
    reasoning: str
