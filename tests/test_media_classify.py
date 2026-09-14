"""`kind` selects a renderer. It must never be `other` for something we can render."""

import pytest

from media_mcp.classify import KIND_ORDER, classify

CASES = [
    ("image/png", "image"),
    ("image/svg+xml", "image"),
    ("video/mp4", "video"),
    ("video/quicktime", "video"),
    ("audio/wav", "audio"),
    ("audio/mpeg", "audio"),
    ("application/pdf", "pdf"),
    ("text/markdown", "text"),
    ("text/plain", "text"),
    ("application/json", "text"),
    ("application/octet-stream", "other"),
    ("application/zip", "other"),
]


@pytest.mark.parametrize("mime,expected", CASES)
def test_kind_is_derived_from_the_mime_family(mime: str, expected: str):
    assert classify(mime) == expected


def test_every_kind_has_a_renderer_in_the_documented_order():
    assert KIND_ORDER == ("image", "video", "audio", "pdf", "text", "other")


def test_an_unknown_mime_is_never_guessed_into_a_media_kind():
    """Guessing would make the renderer pick a player that cannot play it."""
    assert classify("application/vnd.ms-excel") == "other"
