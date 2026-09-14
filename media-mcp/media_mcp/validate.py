"""The six gates a path must pass before a reference is minted.

Ordered cheapest-first, and ordered so the message the model receives names the thing it
can actually fix. The size gate is last because it is the only one that has to stat the
file twice on a large artefact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .reference import reference_for


@dataclass(frozen=True)
class Rejection:
    reason: str
    detail: str
    hint: str

    def as_dict(self) -> dict:
        return {"reason": self.reason, "detail": self.detail, "hint": self.hint}


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except (ValueError, OSError):
        return False
    return True


def _drive(path: Path) -> str:
    return path.resolve(strict=False).drive.lower()


def validate(raw_path: str, cfg: Config) -> Rejection | None:
    if not raw_path or not raw_path.strip():
        return Rejection("not-absolute", "路径为空", "传一个绝对路径")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        return Rejection(
            "not-absolute", f"{raw_path} 不是绝对路径", "传一个绝对路径（含盘符）"
        )

    if not candidate.exists():
        return Rejection("missing", f"{raw_path} 不存在", "确认路径无误后重试")

    if not candidate.is_file():
        return Rejection("not-a-file", f"{raw_path} 不是普通文件", "只能发布文件，不能发布目录")

    if not any(_is_within(candidate, root) for root in cfg.roots):
        allowed = "；".join(root.as_posix() for root in cfg.roots)
        return Rejection(
            "outside-root",
            f"{raw_path} 不在允许发布的根目录内",
            f"允许的根目录：{allowed}",
        )

    if _drive(candidate) != _drive(cfg.fs_cwd):
        return Rejection(
            "wrong-drive",
            f"{raw_path} 与文件系统基准 {cfg.fs_cwd.as_posix()} 不在同一个盘符",
            "引用形式不带盘符，宿主只能从 fs.cwd 取盘符；把文件放到同一盘符下",
        )

    if reference_for(candidate) is None:
        return Rejection(
            "unreferenceable",
            f"{raw_path} 的路径含空格/括号/中文，或无法形成同源引用",
            "把它复制到一个只用 ASCII、无空格的名字下再发布",
        )

    try:
        size = candidate.stat().st_size
    except OSError as error:
        return Rejection("missing", f"无法读取 {raw_path}：{error}", "确认文件可读")

    if size > cfg.max_bytes:
        return Rejection(
            "too-large",
            f"文件 {size} 字节，超过上限 {cfg.max_bytes} 字节",
            "压缩或切片后再发布；不要重复重试",
        )

    return None
