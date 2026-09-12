"""Shared fakes: pipeline, declarative, and render tests all need them."""

from __future__ import annotations

import json
from pathlib import Path

from manim_mcp.config import Config
from manim_mcp.engine import render
from manim_mcp.engine.diagnostics import Diagnostic
from manim_mcp.engine.postprocess import Preview


def make_config(render_root: Path, **overrides) -> Config:
    base = dict(
        python=r"D:\py\python.exe",
        manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe",
        render_root=render_root,
        max_concurrency=1,
        timeout_sec=30.0,
        gif_target_bytes=1000,
        gif_max_bytes=2000,
        keep_runs=50,
        log_level="INFO",
    )
    base.update(overrides)
    return Config(**base)


def stub_render(ok: bool, *, diagnostic: Diagnostic | None = None, seconds: float = 3.0):
    """A render callable that fabricates an artifact instead of running Manim."""

    def fake(cfg, paths, scene_name, quality, **kwargs):
        if ok:
            artifact = paths.out / f"{scene_name}.mp4"
            artifact.write_bytes(b"mp4")
            return render.RenderResult(ok=True, mp4=artifact, seconds=seconds)
        return render.RenderResult(
            ok=False,
            mp4=None,
            seconds=seconds,
            diagnostic=diagnostic or Diagnostic(stage="manim", message="boom"),
        )

    return fake


def stub_preview(kind: str | None = "gif", size: int = 800):
    """A preview callable that fabricates one artifact of the requested kind."""

    def fake(ffmpeg, mp4, out_dir, basename, *, target_bytes, max_bytes, **kwargs):
        if kind is None:
            return Preview(
                path=None,
                kind=None,
                byte_size=0,
                warnings=("ffmpeg 不可用，未生成预览图",),
            )
        path = out_dir / f"{basename}.{kind}"
        path.write_bytes(b"x" * size)
        return Preview(path=path, kind=kind, byte_size=size)

    return fake


def text_of(blocks) -> dict:
    """The JSON payload from a tool's first (text) content block."""
    return json.loads(blocks[0].text)
