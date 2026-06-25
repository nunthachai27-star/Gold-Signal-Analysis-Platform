from datetime import datetime, timezone
from app.domain import Candle, SignalDecision


def test_candle_fields():
    c = Candle("XAU_USD", "M5", datetime(2024, 1, 1, tzinfo=timezone.utc),
               1.0, 2.0, 0.5, 1.5)
    assert c.close == 1.5 and c.volume == 0.0


def test_signal_decision_fields():
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 60, 40, "Normal", "because")
    assert d.direction == "BUY" and d.tp2 == 2020
