"""Invoke the Manim CLI and collect its artifact.

The child is spawned in its own process group so a timeout can take down the
whole tree: Manim forks `latex`, `dvisvgm`, and `ffmpeg`, and killing only the
parent would leave those holding the CPU and the output files.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .. import config as config_mod
from . import diagnostics

QUALITY_FLAG = {"draft": "-ql", "final": "-qm"}

KILL_TIMEOUT_SEC = 10


@dataclass(frozen=True)
class RenderResult:
    """Outcome of one Manim invocation."""

    ok: bool
    mp4: Path | None
    seconds: float
    diagnostic: diagnostics.Diagnostic | None = None


def build_argv(cfg: config_mod.Config, paths, scene_name: str, quality: str) -> list[str]:
    """The exact command line for one render."""
    flag = QUALITY_FLAG.get(quality)
    if flag is None:
        raise ValueError(
            f"unknown quality {quality!r}; expected one of {sorted(QUALITY_FLAG)}"
        )
    return config_mod.manim_argv(
        cfg,
        "render",
        flag,
        "--format=mp4",
        "--media_dir", str(paths.media),
        "--output_file", scene_name,
        str(paths.scene),
        scene_name,
    )


def find_output_mp4(media_dir: Path, scene_name: str) -> Path | None:
    """Newest `videos/**/<scene>.mp4` under the media dir, or None.

    The intermediate directories encode the module stem and the quality label, so
    globbing is more durable than reconstructing that path.
    """
    try:
        candidates = [
            path for path in media_dir.glob(f"videos/**/{scene_name}.mp4") if path.is_file()
        ]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _kill_tree(process, run=None) -> None:
    """Terminate the child and everything it spawned."""
    if process.poll() is not None:
        return
    runner = run or subprocess.run
    if os.name == "nt":
        try:
            runner(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
        except OSError:  # pragma: no cover - taskkill is present on Windows
            process.kill()
    else:  # pragma: no cover - the deployment target is Windows
        process.kill()
    try:
        process.wait(timeout=KILL_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        pass


def render_scene(
    cfg: config_mod.Config,
    paths,
    scene_name: str,
    quality: str,
    *,
    popen=None,
    run=None,
) -> RenderResult:
    """Render one scene, converting every failure mode into a RenderResult."""
    argv = build_argv(cfg, paths, scene_name, quality)
    spawn = popen or subprocess.Popen
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0

    started = time.monotonic()
    try:
        process = spawn(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
    except OSError as error:
        # A pinned-but-missing binary is a realistic failure (install.ps1 writes
        # absolute paths, and the user can move Python or Manim afterwards). A
        # traceback escaping here would reach the model as an unactionable crash.
        return RenderResult(
            ok=False,
            mp4=None,
            seconds=time.monotonic() - started,
            diagnostic=diagnostics.Diagnostic(
                stage="manim",
                type=type(error).__name__,
                message=f"无法启动 Manim 进程：{error}",
                hint=(
                    "Manim 可执行文件不存在或不可执行。检查 MANIM_MCP_MANIM 与 "
                    "MANIM_MCP_PYTHON 指向的路径是否正确，或重新运行 install.ps1 "
                    "重新探测绝对路径。"
                ),
            ),
        )

    timed_out = False
    stderr = ""
    try:
        _, stderr = process.communicate(timeout=cfg.timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(process, run=run)
        try:
            _, stderr = process.communicate(timeout=KILL_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            stderr = ""
    elapsed = time.monotonic() - started

    if timed_out:
        return RenderResult(
            ok=False,
            mp4=None,
            seconds=elapsed,
            diagnostic=diagnostics.Diagnostic(
                stage="timeout",
                message=f"渲染超过 {cfg.timeout_sec:g} 秒，进程树已终止",
                stderr_tail=diagnostics.tail(diagnostics.strip_noise(stderr or "")),
            ),
        )

    mp4 = find_output_mp4(paths.media, scene_name)
    if process.returncode == 0 and mp4 is not None:
        return RenderResult(ok=True, mp4=mp4, seconds=elapsed)

    if process.returncode == 0:
        return RenderResult(
            ok=False,
            mp4=None,
            seconds=elapsed,
            diagnostic=diagnostics.Diagnostic(
                stage="manim",
                message=(
                    f"manim 退出码为 0，但没有找到产物 {scene_name}.mp4"
                    "（通常是场景类没有被真正执行）"
                ),
                stderr_tail=diagnostics.tail(diagnostics.strip_noise(stderr or "")),
            ),
        )

    diagnostic = diagnostics.classify(stderr or "", paths.scene, stage="manim")
    if diagnostic.type is None:
        diagnostic = diagnostics.Diagnostic(
            stage="manim",
            message=f"manim 退出码 {process.returncode}",
            stderr_tail=diagnostic.stderr_tail,
        )
    return RenderResult(ok=False, mp4=mp4, seconds=elapsed, diagnostic=diagnostic)
