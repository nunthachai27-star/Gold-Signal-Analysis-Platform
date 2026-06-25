from datetime import datetime, timezone, timedelta
from app.domain import Candle
from app.analysis.indicators import compute_indicators


def _series(prices):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    out = []
    for i, p in enumerate(prices):
        out.append(Candle("XAU_USD", "H1", base + timedelta(hours=i),
                           open=p, high=p + 1, low=p - 1, close=p, volume=1))
    return out


def test_uptrend_detected():
    candles = _series([2000 + i for i in range(120)])  # steadily rising
    ind = compute_indicators(candles, ema_fast=10, ema_slow=30, swing_lookback=10)
    assert ind.trend == "up"
    assert ind.ema_fast > ind.ema_slow
    assert ind.swing_high >= ind.swing_low
    assert ind.timeframe == "H1"


def test_downtrend_detected():
    candles = _series([2200 - i for i in range(120)])  # steadily falling
    ind = compute_indicators(candles, ema_fast=10, ema_slow=30, swing_lookback=10)
    assert ind.trend == "down"
    assert ind.ema_fast < ind.ema_slow


def test_fields_never_nan():
    candles = _series([2000 + (i % 5) for i in range(60)])
    ind = compute_indicators(candles, ema_fast=10, ema_slow=30)
    for v in [ind.ema_fast, ind.ema_slow, ind.rsi, ind.macd,
              ind.macd_signal, ind.atr]:
        assert v == v  # not NaN
