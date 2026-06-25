from datetime import datetime, timezone, timedelta
from app.domain import Candle, SignalDecision
from app.config import Settings
from app.db.session import make_engine, init_db, make_session_factory
from app.repository import Repository
from app.pipeline import run_cycle

NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


class FakeProvider:
    def get_candles(self, symbol, timeframe, count=250):
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [Candle(symbol, timeframe, base + timedelta(hours=i),
                       2000 + i, 2001 + i, 1999 + i, 2000 + i, 1)
                for i in range(120)]


class FakeAnalyzer:
    def __init__(self, decision):
        self.decision = decision

    def analyze(self, snapshot):
        return self.decision


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def make_repo():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return Repository(make_session_factory(engine))


def settings():
    return Settings(timeframes="D1,M5", signal_threshold=55, cooldown_min=30)


def test_valid_signal_is_sent_and_saved():
    repo = make_repo()
    repo.add_recipient("123")
    decision = SignalDecision("BUY", 2119, 2110, 2130, 2140, 62, 38, "Normal", "r")
    notifier = FakeNotifier()
    result = run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier,
                       repo, settings(), NOW)
    assert result["status"] == "sent"
    assert len(notifier.sent) == 1
    assert repo.get_last_signal("XAU_USD").direction == "BUY"


def test_rejected_signal_not_sent():
    repo = make_repo()
    repo.add_recipient("123")
    decision = SignalDecision("NONE", 0, 0, 0, 0, 50, 50, "Normal", "")
    notifier = FakeNotifier()
    result = run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier,
                       repo, settings(), NOW)
    assert result["status"] == "rejected"
    assert notifier.sent == []


def test_duplicate_within_cooldown_skipped():
    repo = make_repo()
    repo.add_recipient("123")
    decision = SignalDecision("BUY", 2119, 2110, 2130, 2140, 62, 38, "Normal", "r")
    notifier = FakeNotifier()
    run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier, repo,
              settings(), NOW)
    result = run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier, repo,
                       settings(), NOW + timedelta(minutes=5))
    assert result["status"] == "skipped"
    assert len(notifier.sent) == 1  # only the first one
