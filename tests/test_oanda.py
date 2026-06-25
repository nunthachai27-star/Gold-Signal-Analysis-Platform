from app.providers.oanda import OandaProvider

SAMPLE = {
    "candles": [
        {"complete": True, "time": "2024-01-02T00:00:00.000000000Z",
         "volume": 10, "mid": {"o": "2050.1", "h": "2060.2", "l": "2045.0",
                               "c": "2055.5"}},
        {"complete": False, "time": "2024-01-03T00:00:00.000000000Z",
         "volume": 3, "mid": {"o": "2055.5", "h": "2058.0", "l": "2054.0",
                              "c": "2057.0"}},
    ]
}


def test_parse_skips_incomplete_and_maps_fields():
    candles = OandaProvider._parse("XAU_USD", "D1", SAMPLE)
    assert len(candles) == 1
    c = candles[0]
    assert c.close == 2055.5 and c.high == 2060.2
    assert c.timeframe == "D1" and c.symbol == "XAU_USD"
    assert c.time.year == 2024 and c.time.hour == 0


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        return _FakeResp(self.payload)


def test_get_candles_calls_correct_endpoint():
    sess = _FakeSession(SAMPLE)
    p = OandaProvider("tok", env="practice", session=sess)
    candles = p.get_candles("XAU_USD", "H4", count=100)
    assert len(candles) == 1
    url, params, headers = sess.calls[0]
    assert "instruments/XAU_USD/candles" in url
    assert params["granularity"] == "H4" and params["count"] == 100
    assert headers["Authorization"] == "Bearer tok"
    assert "api-fxpractice.oanda.com" in url
