"""Run-directory lifecycle: naming, layout, metadata, retention.

A run id is the only thing the gallery, the tool envelope, and the on-disk layout
all agree on, so it is generated here and validated everywhere it is accepted.
Names are deliberately ASCII-only: a space, bracket, or CJK character in the path
would break the Markdown image syntax the preview channel depends on.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4,8}$")
META_NAME = "run.json"


class WorkspaceError(RuntimeError):
    """A run directory cannot be prepared or read."""


@dataclass(frozen=True)
class RunPaths:
    """Every path one run owns."""

    run_id: str
    root: Path
    media: Path
    out: Path
    scene: Path

    @property
    def meta(self) -> Path:
        return self.root / META_NAME


def new_run_id(now: datetime | None = None, token: str | None = None) -> str:
    """`YYYYMMDD-HHMMSS-xxxxxxxx`, which sorts chronologically as a plain string.

    32 bits of suffix entropy, not 16: renders are serialised but a fast scene can
    finish inside one second, and a collision would silently overwrite the earlier
    run's directory. The validator accepts 4-8 hex characters so short ids written
    by hand or baked into fixtures stay usable.
    """
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    suffix = token if token is not None else secrets.token_hex(4)
    return f"{stamp}-{suffix}"


def is_valid_run_id(value: str) -> bool:
    return bool(RUN_ID_PATTERN.match(value or ""))


def run_paths(root: Path, run_id: str) -> RunPaths:
    """Describe a run's paths without touching the filesystem."""
    base = root / run_id
    return RunPaths(
        run_id=run_id,
        root=base,
        media=base / "media",
        out=base / "out",
        scene=base / "scene.py",
    )


def prepare_run(root: Path, run_id: str) -> RunPaths:
    """Validate the id and materialise the run tree."""
    if not is_valid_run_id(run_id):
        raise WorkspaceError(
            f"invalid run id {run_id!r}: expected YYYYMMDD-HHMMSS-xxxx "
            "(lowercase hex, ASCII only)"
        )
    paths = run_paths(root, run_id)
    try:
        for directory in (paths.media, paths.out):
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise WorkspaceError(f"cannot create run directory {paths.root}: {error}") from error
    return paths


def write_scene(paths: RunPaths, code: str) -> Path:
    try:
        paths.scene.write_text(code, encoding="utf-8")
    except OSError as error:
        raise WorkspaceError(f"cannot write {paths.scene}: {error}") from error
    return paths.scene


def read_scene(paths: RunPaths) -> str:
    return paths.scene.read_text(encoding="utf-8")


def write_meta(paths: RunPaths, data: dict) -> Path:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        paths.meta.write_text(payload, encoding="utf-8")
    except OSError as error:
        raise WorkspaceError(f"cannot write {paths.meta}: {error}") from error
    return paths.meta


def read_meta_at(run_dir: Path) -> dict | None:
    """Tolerant read: a missing, corrupt, or non-object run.json is simply absent."""
    try:
        raw = json.loads((run_dir / META_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def read_meta(paths: RunPaths) -> dict | None:
    return read_meta_at(paths.root)


def existing_run_ids(root: Path) -> list[str]:
    """Valid run ids under `root`, newest first. A missing root is empty."""
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    found = [
        child.name
        for child in children
        if child.is_dir() and is_valid_run_id(child.name)
    ]
    found.sort(reverse=True)
    return found


def prune_runs(root: Path, keep: int) -> list[str]:
    """Delete the oldest runs beyond `keep`. `keep <= 0` means keep everything."""
    if keep <= 0:
        return []
    ids = existing_run_ids(root)
    doomed = ids[keep:]
    removed: list[str] = []
    for run_id in doomed:
        try:
            shutil.rmtree(root / run_id, ignore_errors=False)
        except OSError:
            continue
        removed.append(run_id)
    return removed
