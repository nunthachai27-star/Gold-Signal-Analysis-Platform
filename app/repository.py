from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db.models import PriceCandle, SignalHistory, Recipient
from app.domain import Candle, SignalDecision


class Repository:
    def __init__(self, session_factory):
        self._sf = session_factory

    def save_candles(self, candles: list[Candle]) -> int:
        added = 0
        with self._sf() as s:
            for c in candles:
                row = PriceCandle(
                    symbol=c.symbol, timeframe=c.timeframe, candle_time=c.time,
                    open=c.open, high=c.high, low=c.low, close=c.close,
                    volume=c.volume,
                )
                s.add(row)
                try:
                    s.commit()
                    added += 1
                except IntegrityError:
                    s.rollback()
        return added

    def add_recipient(self, chat_id: str, name: str = "") -> None:
        with self._sf() as s:
            s.add(Recipient(telegram_chat_id=chat_id, name=name, is_active=True,
                            created_at=datetime.now(timezone.utc)))
            s.commit()

    def get_active_recipients(self) -> list[str]:
        with self._sf() as s:
            rows = s.execute(
                select(Recipient).where(Recipient.is_active.is_(True))
            ).scalars().all()
            return [r.telegram_chat_id for r in rows]

    def get_last_signal(self, symbol: str) -> SignalHistory | None:
        with self._sf() as s:
            return s.execute(
                select(SignalHistory)
                .where(SignalHistory.symbol == symbol)
                .order_by(SignalHistory.generated_at.desc())
            ).scalars().first()

    def save_signal(self, symbol: str, decision: SignalDecision, summary: str,
                    snapshot_json: str, generated_at: datetime) -> SignalHistory:
        with self._sf() as s:
            row = SignalHistory(
                symbol=symbol, signal_type=decision.type,
                direction=decision.direction, entry_price=decision.entry,
                stop_loss=decision.sl, take_profit_1=decision.tp1,
                take_profit_2=decision.tp2, buy_probability=decision.buy_prob,
                sell_probability=decision.sell_prob, timeframe_summary=summary,
                reasoning=decision.reasoning, snapshot_json=snapshot_json,
                generated_at=generated_at, status="sent",
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            return row
