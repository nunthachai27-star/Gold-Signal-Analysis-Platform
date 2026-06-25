from datetime import datetime


def should_send(direction: str, last_direction: str | None,
                last_time: datetime | None, now: datetime,
                cooldown_min: int) -> bool:
    if last_direction is None or last_time is None:
        return True
    if direction != last_direction:
        return True
    elapsed_min = (now - last_time).total_seconds() / 60
    return elapsed_min >= cooldown_min
