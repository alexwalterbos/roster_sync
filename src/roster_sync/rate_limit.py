from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import time


@dataclass(slots=True)
class GlobalDebounceDecision:
    allowed_now: bool
    wait_seconds: float


def check_global_debounce(
    last_request_at: datetime | None,
    now: datetime,
    min_interval_seconds: int,
) -> GlobalDebounceDecision:
    if last_request_at is None:
        return GlobalDebounceDecision(allowed_now=True, wait_seconds=0.0)

    elapsed = (now - last_request_at).total_seconds()
    wait_seconds = max(0.0, min_interval_seconds - elapsed)
    return GlobalDebounceDecision(
        allowed_now=wait_seconds == 0.0,
        wait_seconds=wait_seconds,
    )


def is_page_fetch_allowed(page_debounce_until: datetime, now: datetime) -> bool:
    return now >= page_debounce_until


def wait_for_global_debounce(wait_seconds: float) -> None:
    if wait_seconds > 0:
        time.sleep(wait_seconds)
