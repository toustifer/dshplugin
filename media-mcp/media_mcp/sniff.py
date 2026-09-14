"""Identify a file's media type from its extension and its first bytes.

Two sources, deliberately: the extension is what the user meant, the magic is what the
file is. The renderer picks an element from the type — a PDF handed to `<video>` fails
silently in the browser — so a disagreement is resolved in favour of the bytes and
reported in `warnings`.
"""

from __future__ import annotations

from pathlib import Path

OCTET_STREAM = "application/octet-stream"

EXTENSION_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".csv": "text/csv",
    ".html": "text/html",
    ".htm": "text/html",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/plain",
}

# (magic, offset, mime). Longest/most specific first: `RIFF` alone is not enough.
MAGIC: tuple[tuple[bytes, int, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"RIFF", 0, "audio/wav"),  # refined below; RIFF also fronts WebP/AVI
    (b"%PDF-", 0, "application/pdf"),
    (b"fLaC", 0, "audio/flac"),
    (b"OggS", 0, "audio/ogg"),
    (b"ID3", 0, "audio/mpeg"),
    (b"\xff\xfb", 0, "audio/mpeg"),
    (b"ftyp", 4, "video/mp4"),
    (b"WEBP", 8, "image/webp"),
)


def _from_magic(head: bytes) -> str | None:
    for magic, offset, mime in MAGIC:
        if head[offset : offset + len(magic)] == magic:
            if mime == "audio/wav" and head[8:12] == b"WEBP":
                return "image/webp"
            if mime == "audio/wav" and head[8:12] == b"AVI ":
                return "video/x-msvideo"
            return mime
    return None


def sniff(path: Path) -> tuple[str, list[str]]:
    """Return `(mime, warnings)`. Never raises for an unreadable file — the caller
    validates existence first, and a zero-length read is a legitimate answer."""
    try:
        head = path.read_bytes()[:32]
    except OSError:
        head = b""

    by_extension = EXTENSION_MIME.get(path.suffix.lower())
    by_magic = _from_magic(head)

    warnings: list[str] = []
    if by_magic is not None and by_extension is not None and by_magic != by_extension:
        warnings.append(
            f"扩展名 {path.suffix} 声明 {by_extension}，实际内容像 {by_magic}；以内容为准"
        )
    if by_magic is not None:
        return by_magic, warnings
    if by_extension is not None:
        return by_extension, warnings
    return OCTET_STREAM, warnings
