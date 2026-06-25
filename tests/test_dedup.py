from datetime import datetime, timezone, timedelta
from app.analysis.dedup import should_send

NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_first_signal_sends():
    assert should_send("BUY", None, None, NOW, 30) is True


def test_direction_change_sends():
    last = NOW - timedelta(minutes=5)
    assert should_send("SELL", "BUY", last, NOW, 30) is True


def test_same_direction_within_cooldown_blocked():
    last = NOW - timedelta(minutes=10)
    assert should_send("BUY", "BUY", last, NOW, 30) is False


def test_same_direction_after_cooldown_sends():
    last = NOW - timedelta(minutes=31)
    assert should_send("BUY", "BUY", last, NOW, 30) is True
