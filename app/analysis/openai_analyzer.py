import json
from app.analysis.base import Analyzer
from app.domain import SignalDecision

SYSTEM_PROMPT = (
    "You are an expert XAUUSD (gold) multi-timeframe technical analyst. "
    "You receive a JSON snapshot of indicators across timeframes "
    "(D1, H4, H1, M15, M5). Decide a single actionable trade.\n"
    "Rules:\n"
    "- Use higher timeframes (D1/H4/H1) for directional bias and lower "
    "timeframes (M15/M5) for entry timing.\n"
    "- If timeframes conflict and there is no clear edge, return direction "
    "\"NONE\".\n"
    "- For BUY: sl < entry < tp1 < tp2. For SELL: sl > entry > tp1 > tp2.\n"
    "- entry must be near current_price.\n"
    "- buy_prob + sell_prob must equal 100.\n"
    "- type is \"Scalp\" when driven mainly by M15/M5, otherwise \"Normal\".\n"
    "- Base sl/tp distances on the provided atr and swing levels.\n"
    "Return ONLY the structured JSON object."
)

SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "direction": {"type": "string", "enum": ["BUY", "SELL", "NONE"]},
        "entry": {"type": "number"},
        "sl": {"type": "number"},
        "tp1": {"type": "number"},
        "tp2": {"type": "number"},
        "buy_prob": {"type": "number"},
        "sell_prob": {"type": "number"},
        "type": {"type": "string", "enum": ["Scalp", "Normal"]},
        "reasoning": {"type": "string"},
    },
    "required": ["direction", "entry", "sl", "tp1", "tp2", "buy_prob",
                 "sell_prob", "type", "reasoning"],
    "additionalProperties": False,
}


class OpenAiAnalyzer(Analyzer):
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def analyze(self, snapshot: dict) -> SignalDecision:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(snapshot)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "signal", "schema": SIGNAL_SCHEMA,
                                "strict": True},
            },
            temperature=0.2,
        )
        data = json.loads(resp.choices[0].message.content)
        return SignalDecision(**data)
