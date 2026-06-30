"""Timezone-aware UTC datetime utilities (R3).

All public functions return datetime objects that are always aware and in UTC.
Collectors must use these instead of datetime.utcnow() (deprecated in 3.12)
or bare datetime.strptime() which produces naive datetimes.
"""
from __future__ import annotations

import time as _time
from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def parse_date(raw: str, formats: tuple[str, ...] = ()) -> datetime:
    """Parse *raw* into a timezone-aware UTC datetime.

    Strategy:
    1. Try ISO 8601 (handles Z, ±HH:MM offsets, and bare date-only strings).
       Naive ISO results are assumed to be UTC.
    2. Try each format in *formats* via strptime; naive results assumed UTC.
    3. Return now_utc() as fallback if every attempt fails.
    """
    if raw:
        # ── 1. ISO 8601 ───────────────────────────────────────────────────
        iso = raw.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso)
            return _ensure_utc(dt)
        except ValueError:
            pass

        # ── 2. caller-supplied strptime formats ───────────────────────────
        for fmt in formats:
            try:
                dt = datetime.strptime(raw.strip(), fmt)
                return _ensure_utc(dt)
            except ValueError:
                continue

    return now_utc()


def from_epoch(ts: int) -> datetime:
    """Convert a Unix epoch (seconds) to an aware UTC datetime."""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def parse_struct_time(st: _time.struct_time) -> datetime:
    """Convert a feedparser ``time.struct_time`` (UTC) to an aware UTC datetime.

    feedparser sets ``published_parsed`` to UTC, so we just attach the tzinfo.
    """
    return datetime(*st[:6], tzinfo=timezone.utc)


def try_parse_date(raw: str, formats: tuple[str, ...] = ()) -> datetime | None:
    """Like parse_date but returns None instead of falling back to now_utc().

    Useful when the caller wants to try multiple candidate strings and only
    fall back to now_utc() after all candidates are exhausted.
    """
    if not raw:
        return None

    iso = raw.strip().replace("Z", "+00:00")
    try:
        return _ensure_utc(datetime.fromisoformat(iso))
    except ValueError:
        pass

    for fmt in formats:
        try:
            return _ensure_utc(datetime.strptime(raw.strip(), fmt))
        except ValueError:
            continue

    return None


def _ensure_utc(dt: datetime) -> datetime:
    """Return *dt* as an aware UTC datetime.

    If *dt* is naive, assume it represents UTC and attach the tzinfo.
    If *dt* has a non-UTC offset, convert it to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
