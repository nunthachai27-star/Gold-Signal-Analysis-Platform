import pandas as pd
from app.domain import Candle, TimeframeIndicators


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, float("nan"))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False).mean()


def _last(series: pd.Series, fallback: float) -> float:
    if series is None or len(series) == 0:
        return fallback
    val = series.iloc[-1]
    return float(val) if val == val else fallback  # NaN check


def compute_indicators(candles: list[Candle], ema_fast: int = 50,
                       ema_slow: int = 200, rsi_len: int = 14,
                       atr_len: int = 14, swing_lookback: int = 20) -> TimeframeIndicators:
    df = pd.DataFrame([{
        "high": c.high, "low": c.low, "close": c.close,
    } for c in candles])

    close = df["close"]
    last_close = float(close.iloc[-1])

    ef = _last(_ema(close, ema_fast), last_close)
    es = _last(_ema(close, ema_slow), last_close)
    rsi = _last(_rsi(close, rsi_len), 50.0)
    atr = _last(_atr(df["high"], df["low"], close, atr_len), 0.0)

    macd_line = _ema(close, 12) - _ema(close, 26)
    macd_signal = _ema(macd_line, 9)
    macd = _last(macd_line, 0.0)
    macd_sig = _last(macd_signal, 0.0)

    window = df.tail(swing_lookback)
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())

    if last_close > ef > es:
        trend = "up"
    elif last_close < ef < es:
        trend = "down"
    else:
        trend = "side"

    return TimeframeIndicators(
        timeframe=candles[-1].timeframe, close=last_close,
        ema_fast=ef, ema_slow=es, rsi=rsi, macd=macd,
        macd_signal=macd_sig, atr=atr,
        swing_high=swing_high, swing_low=swing_low, trend=trend,
    )
