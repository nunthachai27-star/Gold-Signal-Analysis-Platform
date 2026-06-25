import json
import logging
from app.analysis.indicators import compute_indicators
from app.analysis.snapshot import build_snapshot, summarize
from app.analysis.validator import validate_and_filter
from app.analysis.dedup import should_send
from app.notify.telegram import format_signal

log = logging.getLogger("pipeline")


def run_cycle(provider, analyzer, notifier, repo, settings, now) -> dict:
    symbol = settings.symbol
    indicators_by_tf = {}
    current_price = None

    for tf in settings.timeframe_list:
        candles = provider.get_candles(symbol, tf, count=250)
        if not candles:
            continue
        repo.save_candles(candles)
        indicators_by_tf[tf] = compute_indicators(candles)
        current_price = candles[-1].close

    if not indicators_by_tf or current_price is None:
        return {"status": "no_data", "reason": "no candles", "signal_id": None}

    snapshot = build_snapshot(symbol, indicators_by_tf, current_price)
    summary = summarize(indicators_by_tf)

    decision = analyzer.analyze(snapshot)

    ok, reason = validate_and_filter(decision, current_price,
                                     settings.signal_threshold)
    if not ok:
        log.info("signal rejected: %s", reason)
        return {"status": "rejected", "reason": reason, "signal_id": None}

    last = repo.get_last_signal(symbol)
    last_dir = last.direction if last else None
    last_time = last.generated_at if last else None
    if last_time is not None and last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=now.tzinfo)

    if not should_send(decision.direction, last_dir, last_time, now,
                       settings.cooldown_min):
        return {"status": "skipped", "reason": "cooldown", "signal_id": None}

    row = repo.save_signal(symbol, decision, summary, json.dumps(snapshot), now)
    text = format_signal(decision, symbol, summary, now)
    for chat_id in repo.get_active_recipients():
        try:
            notifier.send(chat_id, text)
        except Exception as exc:  # noqa: BLE001
            log.error("telegram send failed for %s: %s", chat_id, exc)

    return {"status": "sent", "reason": "ok", "signal_id": row.id}
