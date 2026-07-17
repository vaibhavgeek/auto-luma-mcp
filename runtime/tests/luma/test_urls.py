from __future__ import annotations

from lumabot_runtime.luma import canonicalize_luma_url


def test_canonicalize_luma_url_removes_tracking_and_fragments() -> None:
    assert (
        canonicalize_luma_url("https://LU.MA/sf-ai-build-night/?utm_source=x&ref=keep#guests")
        == "https://lu.ma/sf-ai-build-night?ref=keep"
    )


def test_canonicalize_relative_luma_url() -> None:
    assert canonicalize_luma_url("/sf-ai-build-night?gclid=abc", "https://lu.ma/sf") == "https://lu.ma/sf-ai-build-night"

