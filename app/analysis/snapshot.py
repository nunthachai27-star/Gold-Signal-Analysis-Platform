from app.domain import TimeframeIndicators


def build_snapshot(symbol: str, indicators_by_tf: dict[str, TimeframeIndicators],
                   current_price: float) -> dict:
    tfs = {}
    for tf, ind in indicators_by_tf.items():
        tfs[tf] = {
            "trend": ind.trend,
            "close": round(ind.close, 3),
            "rsi": round(ind.rsi, 2),
            "macd_state": "bullish" if ind.macd > ind.macd_signal else "bearish",
            "ema_fast": round(ind.ema_fast, 3),
            "ema_slow": round(ind.ema_slow, 3),
            "atr": round(ind.atr, 3),
            "swing_high": round(ind.swing_high, 3),
            "swing_low": round(ind.swing_low, 3),
        }
    return {"symbol": symbol, "current_price": round(current_price, 3),
            "timeframes": tfs}


def summarize(indicators_by_tf: dict[str, TimeframeIndicators]) -> str:
    return " / ".join(f"{tf} {ind.trend}" for tf, ind in indicators_by_tf.items())
