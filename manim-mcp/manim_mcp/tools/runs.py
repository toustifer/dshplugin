"""History: what has been rendered, and the source behind any of it."""

from __future__ import annotations

from pathlib import Path

from ..engine import index, workspace
from . import envelope

DEFAULT_LIMIT = 20
SUMMARY_KEYS = (
    "runId", "tool", "sceneName", "title", "status", "quality",
    "createdAt", "durationSec", "renderSeconds", "assets", "previewUrlPath", "warnings",
)


def _summary(entry: dict) -> dict:
    return {key: entry[key] for key in SUMMARY_KEYS if key in entry}


def _entries(root: Path) -> list[dict]:
    """Prefer the index; rebuild from disk when it is absent or stale-empty."""
    data = index.load_index(root)
    if data["runs"]:
        return data["runs"]
    return index.rebuild_index(root)["runs"]


def list_runs(root: Path, limit: int = DEFAULT_LIMIT) -> dict:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return envelope.plain_payload(
            ok=False, issues=[f"limit 必须是正整数，收到 {limit!r}"], runs=[]
        )
    entries = _entries(root)
    return envelope.plain_payload(
        ok=True,
        count=len(entries),
        shown=min(limit, len(entries)),
        renderRoot=str(root),
        runs=[_summary(entry) for entry in entries[:limit]],
    )


def get_run(root: Path, run_id: str) -> dict:
    if not workspace.is_valid_run_id(run_id):
        return envelope.plain_payload(
            ok=False,
            issues=[f"runId {run_id!r} 格式非法，应为 YYYYMMDD-HHMMSS-xxxx"],
        )
    if not (root / run_id).is_dir():
        return envelope.plain_payload(ok=False, issues=[f"runId {run_id!r} 不存在"])

    paths = workspace.run_paths(root, run_id)
    try:
        source = workspace.read_scene(paths)
    except OSError:
        return envelope.plain_payload(ok=False, issues=[f"{run_id} 的 scene.py 已不存在"])

    return envelope.plain_payload(
        ok=True,
        runId=run_id,
        meta=workspace.read_meta(paths),
        scenePath=str(paths.scene),
        source=source,
    )


def dispatch(root: Path, action: str, run_id: str | None = None, limit: int = DEFAULT_LIMIT) -> dict:
    if action == "list":
        return list_runs(root, limit)
    if action == "get":
        if not run_id:
            return envelope.plain_payload(ok=False, issues=["action=get 需要 run_id"])
        return get_run(root, run_id)
    return envelope.plain_payload(
        ok=False, issues=[f"未知 action {action!r}，可选 list 或 get"]
    )
