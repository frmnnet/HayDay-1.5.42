"""Conversions matching the Mach-O ``LogicTime`` helpers."""
import time

MAGIC_SECONDS_TO_TICKS = 0x3E0F83E1
MAGIC_TICKS_TO_SECONDS = 0x10624DD3


def seconds_to_ticks(seconds):
    """Port of ``LogicTime::getSecondsInTicks``."""
    seconds = max(0, int(seconds or 0))
    scaled = seconds * 10
    high = (scaled * MAGIC_SECONDS_TO_TICKS) >> 32
    quotient = (high >> 4) + (high >> 31)
    return seconds * 15 + quotient


def ticks_to_seconds(ticks):
    """Port of ``LogicTimer::getSecondsLeft``."""
    ticks = max(0, int(ticks or 0))
    if ticks <= 0:
        return 0
    scaled = ticks * 66
    high = (scaled * MAGIC_TICKS_TO_SECONDS) >> 32
    return max(1, (high >> 6) + (high >> 31))


def now_seconds():
    """One integer clock source for server-side deadlines."""
    return int(time.time())


def timer_payload(total_seconds, ready_at, now=None):
    """Build the client's persisted ``LogicTimer`` object.

    ``StartSeconds`` is the original duration while ``TicksLeft`` is relative
    to the current server time.  A finished timer is represented by absence
    of the field, matching LogicTimer::save/LogicField::save.
    """
    now = now_seconds() if now is None else int(now)
    remaining = max(0, int(ready_at) - now)
    if remaining <= 0:
        return None
    return {
        "StartSeconds": max(1, int(total_seconds or remaining)),
        "TicksLeft": seconds_to_ticks(remaining),
    }


def sync_timer(container, key, total_seconds, ready_at, now=None):
    """Update one timer object and remove it once its deadline has passed."""
    if not isinstance(container, dict):
        return None
    timer = timer_payload(total_seconds, ready_at, now)
    if timer is None:
        container.pop(key, None)
    else:
        container[key] = timer
    return timer


def remaining_seconds(timer):
    """Seconds represented by a persisted timer, or zero when invalid."""
    if not isinstance(timer, dict):
        return 0
    try:
        return ticks_to_seconds(timer.get("TicksLeft", 0))
    except (TypeError, ValueError):
        return 0
