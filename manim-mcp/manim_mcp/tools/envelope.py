"""One return shape for every tool.

The text block is what the model reads and can act on; the image block is what the
user sees. Both come from here so no tool can forget one of them, and so the
Markdown fallback path is generated in exactly one place.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from mcp.types import ImageContent, TextContent

from ..engine.diagnostics import Diagnostic
from ..engine.postprocess import MIME_BY_KIND

MARKDOWN_ALT = "anim"
# Markdown image destinations break on whitespace, parentheses, and non-ASCII.
UNSAFE_MARKDOWN_RE = re.compile(r"[\s()<>\"'\u4e00-\u9fff]")
# `D:/...` or `C:/...` — the form a Windows absolute path takes after slash
# normalisation, and the form Node's win32 `normalize` resolves back correctly
# once a single leading slash is prepended.
DRIVE_RE = re.compile(r"^[A-Za-z]:/")

SUPPORTED_IMAGE_MIMES = frozenset(MIME_BY_KIND.values())


def preview_markdown(path: str | Path) -> str | None:
    """The `/D:/...` Markdown image reference the DSH web UI rewrites to `/api/file`.

    Returns None when the path cannot survive Markdown, which is why run ids and
    file names are restricted to ASCII without spaces or brackets.
    """
    text = str(path)
    if not text or UNSAFE_MARKDOWN_RE.search(text):
        return None

    normalized = text.replace("\\", "/")
    if normalized.startswith("//"):
        return None
    if DRIVE_RE.match(normalized):
        normalized = "/" + normalized
    elif not normalized.startswith("/"):
        return None
    return f"![{MARKDOWN_ALT}]({normalized})"


def success_payload(
    *,
    run_id: str,
    scene_name: str,
    assets: dict,
    preview_markdown: str | None,
    duration_sec: float,
    render_seconds: float,
    preview_bytes: int,
    quality: str,
    warnings: list[str],
) -> dict:
    return {
        "ok": True,
        "runId": run_id,
        "sceneName": scene_name,
        "assets": assets,
        "previewMarkdown": preview_markdown,
        "durationSec": round(float(duration_sec), 2),
        "renderSeconds": round(float(render_seconds), 2),
        "previewBytes": int(preview_bytes),
        "quality": quality,
        "warnings": list(warnings),
    }


def failure_payload(
    *,
    run_id: str,
    diagnostic: Diagnostic,
    code_path: str | Path | None = None,
    warnings: list[str] | None = None,
) -> dict:
    payload: dict = {
        "ok": False,
        "runId": run_id,
        "stage": diagnostic.stage,
        "error": diagnostic.as_dict(),
        "hint": diagnostic.hint,
    }
    if code_path is not None:
        payload["codePath"] = str(code_path)
    if warnings:
        payload["warnings"] = list(warnings)
    return payload


def plain_payload(**fields) -> dict:
    """For tools that produce data rather than an artifact (`check`, `runs`, ...)."""
    return {"ok": bool(fields.pop("ok", True)), **fields}


def content_blocks(
    payload: dict,
    preview_path: Path | None = None,
    preview_kind: str | None = None,
) -> list[TextContent | ImageContent]:
    """Text envelope first, then the preview image when one is available."""
    blocks: list[TextContent | ImageContent] = [
        TextContent(
            type="text",
            text=json.dumps(payload, ensure_ascii=False, indent=2),
        )
    ]

    if preview_path is None or preview_kind is None:
        return blocks
    mime = MIME_BY_KIND.get(preview_kind)
    if mime is None or mime not in SUPPORTED_IMAGE_MIMES:
        return blocks
    try:
        data = Path(preview_path).read_bytes()
    except OSError:
        return blocks

    blocks.append(
        ImageContent(
            type="image",
            data=base64.b64encode(data).decode("ascii"),
            mimeType=mime,
        )
    )
    return blocks
