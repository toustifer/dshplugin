"""The JSON the renderer parses. One success shape, one failure shape.

`reference` is computed host-side and copied verbatim by the client, so the rule about
how a path resolves lives in exactly one place.
"""

from __future__ import annotations

from pathlib import Path

from .validate import Rejection


def descriptor(
    path: Path,
    *,
    reference: str,
    kind: str,
    mime: str,
    title: str | None,
    warnings: list[str],
    pages: int | None = None,
) -> dict:
    item: dict = {
        "kind": kind,
        "mime": mime,
        "name": path.name,
        "path": str(path),
        "reference": reference,
        "bytes": path.stat().st_size,
        "warnings": list(warnings),
    }
    if title:
        item["title"] = title
    if pages is not None:
        item["pages"] = pages
    return item


def success(primary: dict, *, extras: list[dict] | None = None, warnings: list[str] | None = None) -> dict:
    return {
        "ok": True,
        "media": primary,
        "extras": list(extras or []),
        "warnings": list(warnings or []),
    }


def failure(rejection: Rejection) -> dict:
    return {"ok": False, **rejection.as_dict()}
