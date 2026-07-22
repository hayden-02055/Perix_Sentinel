"""Unit tests for URL/title normalization (Passthrough Clusterer SDD §5)."""
from app.core.url_utils import canonical_key, normalize_title, normalize_url


def test_normalize_url_lowercases_scheme_and_host():
    assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


def test_normalize_url_strips_trailing_slash_and_fragment():
    assert normalize_url("https://example.com/a/b/#section") == "https://example.com/a/b"


def test_normalize_url_drops_tracking_params_keeps_meaningful():
    got = normalize_url("https://example.com/x?id=7&utm_source=news&ref=hn&page=2")
    assert got == "https://example.com/x?id=7&page=2"


def test_normalize_url_is_query_order_independent():
    a = normalize_url("https://example.com/x?b=2&a=1")
    b = normalize_url("https://example.com/x?a=1&b=2")
    assert a == b


def test_normalize_title_collapses_whitespace_and_case():
    assert normalize_title("  Claude   Science\n") == "claude science"


def test_canonical_key_falls_back_to_title_when_url_blank():
    assert canonical_key("", "Claude Science") == "title:claude science"
    assert canonical_key("   ", "Claude Science") == "title:claude science"
