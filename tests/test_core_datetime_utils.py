"""Characterization tests for app.core.datetime_utils (R3 — RED phase).

All results from parse_date() and parse_struct_time() must be timezone-aware UTC.
now_utc() must return an aware UTC datetime.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from app.core.datetime_utils import from_epoch, now_utc, parse_date, parse_struct_time


# ---------------------------------------------------------------------------
# now_utc
# ---------------------------------------------------------------------------

def test_now_utc_is_aware_utc():
    result = now_utc()
    assert result.tzinfo is not None
    assert result.utcoffset().total_seconds() == 0


def test_now_utc_is_recent():
    before = datetime.now(timezone.utc)
    result = now_utc()
    after = datetime.now(timezone.utc)
    assert before <= result <= after


# ---------------------------------------------------------------------------
# parse_date — ISO 8601 variants (Mistral / HuggingFace / DeepMind)
# ---------------------------------------------------------------------------

def test_parse_date_iso_z_suffix():
    dt = parse_date("2025-04-23T12:00:00Z")
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.hour == 12 and dt.minute == 0


def test_parse_date_iso_with_utc_offset():
    dt = parse_date("2025-04-23T12:00:00+00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23


def test_parse_date_iso_with_positive_offset_normalised_to_utc():
    # "+09:00" is KST; result should be normalised to UTC
    dt = parse_date("2025-04-23T21:00:00+09:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0
    assert dt.hour == 12  # 21:00 KST == 12:00 UTC


def test_parse_date_iso_date_only():
    dt = parse_date("2025-04-23")
    assert dt.tzinfo is not None
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23


def test_parse_date_iso_naive_treated_as_utc():
    # fromisoformat without tz → assume UTC
    dt = parse_date("2025-04-23T12:00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0
    assert dt.hour == 12


# ---------------------------------------------------------------------------
# parse_date — Anthropic format  "%b %d, %Y"
# ---------------------------------------------------------------------------

ANTHROPIC_FORMATS = ("%b %d, %Y",)


def test_parse_date_anthropic_abbr_month():
    dt = parse_date("Apr 23, 2025", ANTHROPIC_FORMATS)
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


def test_parse_date_anthropic_dec():
    dt = parse_date("Dec 01, 2024", ANTHROPIC_FORMATS)
    assert dt.year == 2024 and dt.month == 12 and dt.day == 1
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# parse_date — DeepMind formats
# ---------------------------------------------------------------------------

DEEPMIND_FORMATS = ("%B %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d")


def test_parse_date_deepmind_month_year_only():
    dt = parse_date("April 2025", DEEPMIND_FORMATS)
    assert dt.year == 2025 and dt.month == 4
    assert dt.tzinfo is not None


def test_parse_date_deepmind_full_long():
    dt = parse_date("April 23, 2025", DEEPMIND_FORMATS)
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


def test_parse_date_deepmind_abbr():
    dt = parse_date("Apr 23, 2025", DEEPMIND_FORMATS)
    assert dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


def test_parse_date_deepmind_ymd():
    dt = parse_date("2025-04-23", DEEPMIND_FORMATS)
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# parse_date — Meta formats
# ---------------------------------------------------------------------------

META_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%B %d. %Y", "%b. %d, %Y", "%B %d %Y")


def test_parse_date_meta_long_comma():
    dt = parse_date("April 23, 2025", META_FORMATS)
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


def test_parse_date_meta_abbr_comma():
    dt = parse_date("Apr 23, 2025", META_FORMATS)
    assert dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


def test_parse_date_meta_long_dot():
    dt = parse_date("April 23. 2025", META_FORMATS)
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


def test_parse_date_meta_abbr_dotted():
    dt = parse_date("Apr. 23, 2025", META_FORMATS)
    assert dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


def test_parse_date_meta_no_comma():
    dt = parse_date("April 23 2025", META_FORMATS)
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# parse_date — fallback behaviour
# ---------------------------------------------------------------------------

def test_parse_date_empty_string_returns_now_utc():
    before = datetime.now(timezone.utc)
    dt = parse_date("")
    after = datetime.now(timezone.utc)
    assert dt.tzinfo is not None
    assert before <= dt <= after


def test_parse_date_garbage_returns_now_utc():
    before = datetime.now(timezone.utc)
    dt = parse_date("not a date at all !!!")
    after = datetime.now(timezone.utc)
    assert dt.tzinfo is not None
    assert before <= dt <= after


def test_parse_date_none_like_empty():
    # Collectors sometimes pass empty string when element is missing
    dt = parse_date("")
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# parse_struct_time — OpenAI RSS (feedparser time.struct_time in UTC)
# ---------------------------------------------------------------------------

def test_parse_struct_time_basic():
    # time.struct_time fields: (year, mon, mday, hour, min, sec, wday, yday, isdst)
    st = time.struct_time((2025, 4, 23, 12, 0, 0, 2, 113, 0))
    dt = parse_struct_time(st)
    assert dt.year == 2025 and dt.month == 4 and dt.day == 23
    assert dt.hour == 12 and dt.minute == 0
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0


def test_parse_struct_time_preserves_seconds():
    st = time.struct_time((2024, 12, 31, 23, 59, 45, 0, 366, 0))
    dt = parse_struct_time(st)
    assert dt.second == 45
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# from_epoch (Hacker News `time` field — Unix epoch seconds)
# ---------------------------------------------------------------------------

def test_from_epoch_is_aware_utc():
    dt = from_epoch(1782842392)
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0


def test_from_epoch_known_value():
    # 1782842392 == 2026-06-30T17:59:52Z (verified against HN API sample)
    dt = from_epoch(1782842392)
    assert dt == datetime(2026, 6, 30, 17, 59, 52, tzinfo=timezone.utc)
