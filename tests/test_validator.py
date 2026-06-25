from app.domain import SignalDecision
from app.analysis.validator import validate_and_filter


def buy(buy_prob=62, entry=2000, sl=1990, tp1=2010, tp2=2020):
    return SignalDecision("BUY", entry, sl, tp1, tp2, buy_prob, 100 - buy_prob,
                          "Normal", "r")


def test_valid_buy_passes():
    ok, reason = validate_and_filter(buy(), 2000.0, 55)
    assert ok is True and reason == "ok"


def test_none_direction_rejected():
    d = SignalDecision("NONE", 0, 0, 0, 0, 50, 50, "Normal", "")
    ok, _ = validate_and_filter(d, 2000.0, 55)
    assert ok is False


def test_below_threshold_rejected():
    ok, reason = validate_and_filter(buy(buy_prob=52), 2000.0, 55)
    assert ok is False and reason == "below threshold"


def test_bad_level_order_rejected():
    ok, reason = validate_and_filter(buy(sl=2005), 2000.0, 55)  # sl above entry
    assert ok is False and reason == "bad levels"


def test_prob_sum_invalid_rejected():
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 62, 30, "Normal", "r")
    ok, reason = validate_and_filter(d, 2000.0, 55)
    assert ok is False and reason == "prob sum invalid"


def test_entry_too_far_rejected():
    ok, reason = validate_and_filter(buy(entry=2000), 2500.0, 55)
    assert ok is False and reason == "entry too far from price"
