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
# `D:/...` or `C:/...`.
DRIVE_RE = re.compile(r"^[A-Za-z]:/")

SUPPORTED_IMAGE_MIMES = frozenset(MIME_BY_KIND.values())


def preview_markdown(path: str | Path, render_root: str | Path | None = None) -> str | None:
    """A Markdown image reference the DSH web UI can actually load.

    The renderer accepts exactly two shapes: an `http(s)://` URL, or a same-origin
    path that starts with `/`. A Windows absolute path is therefore unusable — the
    Host resolves the path with `node:path.resolve`, and `/D:/x` becomes
    `C:\\D:\\x`, so the image 404s.

    The shape that *does* work is the absolute path **with the drive letter
    removed**: `D:\\a\\b\\c.gif` becomes `/a/b/c.gif`. Two measured facts make that
    the only workable form:

    * `node:path.resolve('D:\\\\cwd', '/a/b')` is `D:\\a\\b` — for a `/`-rooted
      argument `resolve` discards the cwd's directories entirely and keeps only its
      **drive**. So `/<path from the drive root>` is the reference, and the pinned
      cwd's *directory* is irrelevant.
    * `resolve('D:\\\\cwd', '/D:/a/b')` is `D:\\D:\\a\\b`, and
      `resolve('D:\\\\cwd', '/renders/x')` is `D:\\renders\\x` — neither is the file.

    The invariant this depends on: **the filesystem provider's cwd must sit on the
    same drive as the render root.** `install.ps1` pins `fs-sandbox.cwd` to the
    render root's parent, which satisfies it by construction. Because the artifact
    is always inside the render root, that invariant holds for every reference this
    function returns.

    When the render root is unknown, the artifact lives outside it, or the absolute
    path carries no drive (a UNC or POSIX path the Host cannot reach this way), this
    returns None rather than emitting a reference that would render as a broken image.
    """
    if render_root is None:
        return None

    artifact = Path(path).resolve()
    try:
        artifact.relative_to(Path(render_root).resolve())
    except ValueError:
        return None

    absolute = artifact.as_posix()
    reference = rooted_reference(absolute)
    if reference is None or UNSAFE_MARKDOWN_RE.search(reference):
        return None
    return f"![{MARKDOWN_ALT}]({reference})"


def rooted_reference(absolute_posix: str) -> str | None:
    """Turn an absolute path into the `/`-rooted reference the Host can resolve.

    Split out from :func:`preview_markdown` because the two host shapes are worth
    asserting directly: a Windows path keeps its directories and loses only the
    drive (`D:/a/b` -> `/a/b`), while a POSIX path is already the reference
    (`/a/b` -> `/a/b`). Anything else — a UNC share, a relative path — has no
    same-origin form and yields None.
    """
    if DRIVE_RE.match(absolute_posix):
        return absolute_posix[2:]
    if absolute_posix.startswith("/") and not absolute_posix.startswith("//"):
        return absolute_posix
    return None


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
