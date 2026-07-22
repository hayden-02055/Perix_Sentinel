"""Deterministic URL / title normalization for exact-duplicate clustering.

Passthrough Clusterer SDD §5 (I2/I3). No thresholds — the only merge signal
is an exact match of ``canonical_key``, so normalization must be stable and
lossless of *meaningful* differences while erasing incidental ones (tracking
params, trailing slash, host case, fragment).
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Blacklist, not whitelist (SDD §5): drop known tracking params, keep the rest.
_TRACKING_EXACT: frozenset[str] = frozenset(
    {"ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "yclid"}
)
_TRACKING_PREFIXES: tuple[str, ...] = ("utm_",)

_WS_RE = re.compile(r"\s+")


def _is_tracking(key: str) -> bool:
    k = key.lower()
    return k in _TRACKING_EXACT or any(k.startswith(p) for p in _TRACKING_PREFIXES)


def normalize_url(url: str) -> str:
    """Return a canonical form of *url* (SDD §5 normalize_url rules).

    - scheme + host lowercased
    - fragment (``#...``) removed
    - trailing slash on the path removed
    - tracking query params removed (``utm_*``, ``ref``, ``source``, ``fbclid``, ...)
    - surviving query params sorted (order-independent equality)
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)]
    query = urlencode(sorted(kept))

    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_title(title: str) -> str:
    """Lowercase and collapse whitespace — fallback key for URL-less items (I3)."""
    return _WS_RE.sub(" ", title.strip().lower())


def canonical_key(url: str, title: str) -> str:
    """Deterministic merge key: normalized URL if present, else ``title:``-prefixed title.

    An item is treated as URL-less when *url* is empty/blank (SDD §5, I3).
    """
    if url and url.strip():
        return normalize_url(url)
    return "title:" + normalize_title(title)
