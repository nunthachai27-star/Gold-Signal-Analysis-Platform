from datetime import datetime, timezone
from app.db.session import make_engine, init_db, make_session_factory
from app.domain import Candle, SignalDecision
from app.repository import Repository


def make_repo():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return Repository(make_session_factory(engine))


def test_save_candles_dedupes():
    repo = make_repo()
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    c = Candle("XAU_USD", "M5", t, 1, 2, 0.5, 1.5)
    assert repo.save_candles([c]) == 1
    assert repo.save_candles([c]) == 0  # duplicate ignored


def test_recipients_roundtrip():
    repo = make_repo()
    repo.add_recipient("123", "me")
    assert repo.get_active_recipients() == ["123"]


def test_signal_save_and_last():
    repo = make_repo()
    assert repo.get_last_signal("XAU_USD") is None
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 60, 40, "Normal", "r")
    repo.save_signal("XAU_USD", d, "summary", "{}",
                     datetime(2024, 1, 1, tzinfo=timezone.utc))
    last = repo.get_last_signal("XAU_USD")
    assert last.direction == "BUY"
