from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def canonicalize_luma_url(url: str, base_url: str = "https://lu.ma") -> str:
    absolute = urljoin(base_url, url.strip())
    parts = urlsplit(absolute)
    scheme = "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, netloc, path, query, ""))

