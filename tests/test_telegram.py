from datetime import datetime, timezone
from app.domain import SignalDecision
from app.notify.telegram import TelegramNotifier, format_signal


def test_format_contains_key_lines():
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 62, 38, "Normal", "r")
    text = format_signal(d, "XAU_USD", "D1 up / M5 side",
                         datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert "XAU_USD" in text
    assert "BUY" in text and "2000" in text
    assert "SL" in text and "1990" in text
    assert "TP1" in text and "TP2" in text
    assert "62" in text and "38" in text
    assert "D1 up / M5 side" in text


class _FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"ok": True}


class _FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        return _FakeResp()


def test_send_posts_to_telegram_api():
    sess = _FakeSession()
    n = TelegramNotifier("BOTTOKEN", session=sess)
    n.send("123", "hello")
    url, payload = sess.calls[0]
    assert "botBOTTOKEN/sendMessage" in url
    assert payload == {"chat_id": "123", "text": "hello"}
