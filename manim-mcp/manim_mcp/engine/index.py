"""The `renders/index.json` catalog.

The gallery panel is a read-only consumer of this file and has no other channel
to the server, so the file must be atomic (a reader never sees half a write) and
totally tolerant (any corruption reads as "no runs yet" rather than raising into
a tool call).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

INDEX_NAME = "index.json"
INDEX_VERSION = 1
TEMP_SUFFIX = ".json.tmp"


def index_path(root: Path) -> Path:
    return root / INDEX_NAME


def empty_index() -> dict:
    return {"version": INDEX_VERSION, "updatedAt": None, "runs": []}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_index(root: Path) -> dict:
    """Never raises: an unreadable or malformed index is an empty index."""
    try:
        raw = json.loads(index_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_index()
    if not isinstance(raw, dict) or not isinstance(raw.get("runs"), list):
        return empty_index()
    raw["version"] = raw.get("version", INDEX_VERSION)
    raw.setdefault("updatedAt", None)
    return raw


def save_index(root: Path, data: dict) -> dict:
    """Publish atomically and return exactly what is now on disk.

    Returning the written payload (rather than the path or the input) is what
    keeps `upsert_run`'s return value honest: the caller may log or report it,
    and a stale `updatedAt` there would be a quiet lie.
    """
    target = index_path(root)
    payload = {**data, "version": INDEX_VERSION, "updatedAt": _now_iso()}
    temp = target.with_name(target.name + TEMP_SUFFIX)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp, target)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best effort cleanup
            pass
        raise
    return payload


def upsert_run(root: Path, entry: dict) -> dict:
    """Insert or replace one run, keeping the list newest-first."""
    data = load_index(root)
    run_id = entry.get("runId")
    runs = [run for run in data["runs"] if run.get("runId") != run_id]
    runs.append(entry)
    runs.sort(key=lambda run: str(run.get("createdAt") or ""), reverse=True)
    data["runs"] = runs
    return save_index(root, data)


def remove_run(root: Path, run_id: str) -> dict:
    data = load_index(root)
    data["runs"] = [run for run in data["runs"] if run.get("runId") != run_id]
    return save_index(root, data)


def rebuild_index(root: Path) -> dict:
    """Reconcile the index against the run directories actually on disk.

    The on-disk tree wins: an entry whose directory is gone is dropped, and a
    directory whose metadata is unreadable is skipped rather than invented.
    """
    from . import workspace

    entries: list[dict] = []
    for run_id in workspace.existing_run_ids(root):
        meta = workspace.read_meta_at(root / run_id)
        if meta is None:
            continue
        meta.setdefault("runId", run_id)
        entries.append(meta)

    entries.sort(key=lambda run: str(run.get("createdAt") or ""), reverse=True)
    data = {"version": INDEX_VERSION, "updatedAt": None, "runs": entries}
    if entries or index_path(root).exists():
        save_index(root, data)
    return load_index(root)
