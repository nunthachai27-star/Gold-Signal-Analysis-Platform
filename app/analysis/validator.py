from app.domain import SignalDecision


def validate_and_filter(decision: SignalDecision, current_price: float,
                        threshold: float) -> tuple[bool, str]:
    if decision.direction not in ("BUY", "SELL"):
        return False, "no direction"

    winning = decision.buy_prob if decision.direction == "BUY" else decision.sell_prob
    if winning < threshold:
        return False, "below threshold"

    if abs(decision.buy_prob + decision.sell_prob - 100) > 1:
        return False, "prob sum invalid"

    if decision.direction == "BUY":
        ordered = decision.sl < decision.entry < decision.tp1 < decision.tp2
    else:
        ordered = decision.sl > decision.entry > decision.tp1 > decision.tp2
    if not ordered:
        return False, "bad levels"

    if current_price > 0 and abs(decision.entry - current_price) / current_price > 0.02:
        return False, "entry too far from price"

    return True, "ok"
