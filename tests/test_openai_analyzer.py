import json
from app.analysis.openai_analyzer import OpenAiAnalyzer


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _FakeCompletions:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return _Resp(json.dumps(self.payload))


class _FakeChat:
    def __init__(self, payload):
        self.completions = _FakeCompletions(payload)


class _FakeClient:
    def __init__(self, payload):
        self.chat = _FakeChat(payload)


PAYLOAD = {
    "direction": "BUY", "entry": 2000.0, "sl": 1990.0, "tp1": 2010.0,
    "tp2": 2020.0, "buy_prob": 62.0, "sell_prob": 38.0,
    "type": "Normal", "reasoning": "higher TFs aligned up",
}


def test_analyze_returns_signal_decision():
    client = _FakeClient(PAYLOAD)
    analyzer = OpenAiAnalyzer(client, "gpt-4o-mini")
    snap = {"symbol": "XAU_USD", "current_price": 2000.0, "timeframes": {}}
    decision = analyzer.analyze(snap)
    assert decision.direction == "BUY"
    assert decision.buy_prob == 62.0
    assert decision.type == "Normal"
    assert client.chat.completions.kwargs["model"] == "gpt-4o-mini"
    assert client.chat.completions.kwargs["response_format"]["type"] == "json_schema"
