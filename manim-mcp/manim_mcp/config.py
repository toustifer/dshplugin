"""Configuration and tool discovery.

Every value can be pinned through an environment variable, because the DSH MCP
row hands the child a *scrubbed* environment: anything not passed explicitly may
be absent, including a useful PATH. When nothing is pinned we probe, and when the
probe fails we fall back to a value that still works on this machine.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# <repo>/manim-mcp/manim_mcp/config.py -> parents[2] is <repo>
DEFAULT_RENDER_ROOT = Path(__file__).resolve().parents[2] / "renders"

DEFAULT_TIMEOUT_SEC = 180.0
DEFAULT_GIF_TARGET_BYTES = 8 * 1024 * 1024
DEFAULT_GIF_MAX_BYTES = 18 * 1024 * 1024
DEFAULT_KEEP_RUNS = 50

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

ENV_PREFIX = "MANIM_MCP_"


class ConfigError(ValueError):
    """An environment value is present but unusable."""


@dataclass(frozen=True)
class Config:
    """Resolved run-time settings."""

    python: str
    manim: str | None
    ffmpeg: str | None
    render_root: Path
    max_concurrency: int
    timeout_sec: float
    gif_target_bytes: int
    gif_max_bytes: int
    keep_runs: int
    log_level: str


def _raw(env: Mapping[str, str], name: str) -> str:
    return str(env.get(f"{ENV_PREFIX}{name}", "") or "").strip()


def _read_str(env: Mapping[str, str], name: str, default: str) -> str:
    value = _raw(env, name)
    return value if value else default


def _read_path(env: Mapping[str, str], name: str, default: Path) -> Path:
    value = _raw(env, name)
    return Path(value) if value else default


def _read_int(
    env: Mapping[str, str], name: str, default: int, *, minimum: int = 0
) -> int:
    value = _raw(env, name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigError(
            f"{ENV_PREFIX}{name} must be an integer, got {value!r}"
        ) from error
    if parsed < minimum:
        raise ConfigError(f"{ENV_PREFIX}{name} must be >= {minimum}, got {parsed}")
    return parsed


def _read_float(
    env: Mapping[str, str], name: str, default: float, *, minimum: float = 1.0
) -> float:
    value = _raw(env, name)
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigError(f"{ENV_PREFIX}{name} must be a number, got {value!r}") from error
    if parsed < minimum:
        raise ConfigError(
            f"{ENV_PREFIX}{name} must be >= {minimum:g}, got {parsed:g}"
        )
    return parsed


def _read_log_level(env: Mapping[str, str]) -> str:
    value = _read_str(env, "LOG_LEVEL", "INFO").upper()
    if value not in LOG_LEVELS:
        raise ConfigError(
            f"{ENV_PREFIX}LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}, got {value!r}"
        )
    return value


def resolve_manim(env: Mapping[str, str]) -> str | None:
    """Prefer an explicit binary; otherwise whatever `manim` is on PATH."""
    explicit = _raw(env, "MANIM")
    if explicit:
        return explicit
    return shutil.which("manim")


def resolve_ffmpeg(env: Mapping[str, str]) -> str | None:
    explicit = _raw(env, "FFMPEG")
    if explicit:
        return explicit
    return shutil.which("ffmpeg")


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Build a validated Config. Raises ConfigError on an unusable value."""
    source: Mapping[str, str] = os.environ if env is None else env

    target = _read_int(source, "GIF_TARGET_BYTES", DEFAULT_GIF_TARGET_BYTES, minimum=1)
    hard_max = _read_int(source, "GIF_MAX_BYTES", DEFAULT_GIF_MAX_BYTES, minimum=1)
    if target > hard_max:
        raise ConfigError(
            f"{ENV_PREFIX}GIF_TARGET_BYTES ({target}) must not exceed "
            f"{ENV_PREFIX}GIF_MAX_BYTES ({hard_max})"
        )

    return Config(
        python=_read_str(source, "PYTHON", sys.executable),
        manim=resolve_manim(source),
        ffmpeg=resolve_ffmpeg(source),
        render_root=_read_path(source, "RENDER_ROOT", DEFAULT_RENDER_ROOT),
        max_concurrency=_read_int(source, "MAX_CONCURRENCY", 1, minimum=1),
        timeout_sec=_read_float(source, "TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC, minimum=1.0),
        gif_target_bytes=target,
        gif_max_bytes=hard_max,
        keep_runs=_read_int(source, "KEEP_RUNS", DEFAULT_KEEP_RUNS, minimum=0),
        log_level=_read_log_level(source),
    )


def manim_argv(cfg: Config, *args: str) -> list[str]:
    """Command prefix that runs Manim.

    The `-m manim` form uses the same interpreter that runs this server, so Manim
    is guaranteed importable; it prints one harmless RuntimeWarning that the
    diagnostics layer strips.
    """
    if cfg.manim:
        return [cfg.manim, *args]
    return [cfg.python, "-m", "manim", *args]


def python_argv(cfg: Config, *args: str) -> list[str]:
    """Command prefix that runs Python (used for the self-test scene)."""
    return [cfg.python, *args]


def doctor(cfg: Config) -> list[tuple[str, bool, str]]:
    """Dependency rows for `--selftest` and install-time reporting."""
    latex = shutil.which("latex")
    return [
        ("python", bool(cfg.python), cfg.python),
        (
            "manim",
            cfg.manim is not None,
            cfg.manim or f"{cfg.python} -m manim",
        ),
        ("ffmpeg", cfg.ffmpeg is not None, cfg.ffmpeg or "not found on PATH"),
        ("latex", latex is not None, latex or "not found on PATH"),
        ("render_root", True, str(cfg.render_root)),
    ]
