from app.domain import TimeframeIndicators
from app.analysis.snapshot import build_snapshot, summarize


def _ind(tf, trend, macd, sig):
    return TimeframeIndicators(tf, 2000, 2001, 1999, 55, macd, sig, 5,
                               2010, 1990, trend)


def test_snapshot_structure():
    ind = {"D1": _ind("D1", "up", 1.0, 0.5), "M5": _ind("M5", "side", -1.0, 0.0)}
    snap = build_snapshot("XAU_USD", ind, 2000.0)
    assert snap["symbol"] == "XAU_USD"
    assert snap["current_price"] == 2000.0
    assert snap["timeframes"]["D1"]["macd_state"] == "bullish"
    assert snap["timeframes"]["M5"]["macd_state"] == "bearish"
    assert snap["timeframes"]["D1"]["trend"] == "up"


def test_summarize_format():
    ind = {"D1": _ind("D1", "up", 1, 0), "M5": _ind("M5", "side", 1, 0)}
    assert summarize(ind) == "D1 up / M5 side"
