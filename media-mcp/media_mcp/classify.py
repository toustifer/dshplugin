"""Map a MIME type to the renderer that owns it.

Deliberately total and dumb: `other` is the honest answer for anything we have no
element for, and a wrong guess shows the user a broken player instead of a file row.
"""

from __future__ import annotations

KIND_ORDER = ("image", "video", "audio", "pdf", "text", "other")

_EXACT = {
    "application/pdf": "pdf",
    "application/json": "text",
    "application/xml": "text",
}

_PREFIX = (
    ("image/", "image"),
    ("video/", "video"),
    ("audio/", "audio"),
    ("text/", "text"),
)


def classify(mime: str) -> str:
    normalized = (mime or "").split(";")[0].strip().lower()
    if normalized in _EXACT:
        return _EXACT[normalized]
    for prefix, kind in _PREFIX:
        if normalized.startswith(prefix):
            return kind
    return "other"
