import requests
from app.domain import SignalDecision
from app.notify.base import Notifier


def format_signal(decision: SignalDecision, symbol: str, summary: str,
                  generated_at) -> str:
    return (
        f"\U0001F4C8 {symbol} Signal ({decision.type})\n"
        f"{decision.direction} {decision.entry:g}\n"
        f"SL {decision.sl:g}\n"
        f"TP1 {decision.tp1:g}\n"
        f"TP2 {decision.tp2:g}\n"
        f"BUY win probability: {decision.buy_prob:g}%\n"
        f"SELL win probability: {decision.sell_prob:g}%\n"
        f"Timeframe Bias: {summary}\n"
        f"Time: {generated_at:%Y-%m-%d %H:%M UTC}"
    )


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, session=None):
        self.bot_token = bot_token
        self.session = session or requests.Session()

    def send(self, chat_id: str, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        resp = self.session.post(url, json={"chat_id": chat_id, "text": text},
                                 timeout=10)
        resp.raise_for_status()
