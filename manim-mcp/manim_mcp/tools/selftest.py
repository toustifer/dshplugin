"""`--selftest`: render one real scene and report the whole chain.

install.ps1 runs this so a broken LaTeX install, a missing ffmpeg, or a bad render
root is discovered at install time rather than by a confused model later.
"""

from __future__ import annotations

from typing import Callable

from .. import config as config_mod
from .. import style as style_mod
from ..engine import postprocess, render, workspace
from . import envelope

SAMPLE_SCENE_CLASS = "SelftestScene"

_SCENE = '''from manim import *

@@PREAMBLE@@


class SelftestScene(Scene):
    def construct(self):
        heading = cn("自检通过：中文渲染正常", TITLE_SIZE, WHITE).to_edge(UP, buff=0.8)
        formula = MathTex(r"e^{i\\pi} + 1 = 0")
        formula.next_to(heading, DOWN, buff=0.8)
        ring = Circle(radius=1.1, color=C_BLUE).next_to(formula, DOWN, buff=0.6)

        self.play(Write(heading), run_time=PLAY_RUN_TIME)
        self.play(FadeIn(formula, shift=UP * 0.4), run_time=PLAY_RUN_TIME)
        self.play(Create(ring), run_time=PLAY_RUN_TIME)
        self.wait(TAIL_WAIT)
'''


def sample_scene(cjk_font: str | None) -> str:
    return _SCENE.replace("@@PREAMBLE@@", style_mod.preamble(cjk_font))


def _dependency_problems(cfg: config_mod.Config) -> list[str]:
    problems: list[str] = []
    if not cfg.ffmpeg:
        problems.append("找不到 ffmpeg：GIF 预览无法生成（可用 MANIM_MCP_FFMPEG 显式指定绝对路径）")
    if not cfg.python:
        problems.append("找不到 Python 解释器")
    return problems


def run(
    cfg: config_mod.Config,
    *,
    build_code: Callable[[], str] | None = None,
    render_fn=None,
    preview_fn=None,
) -> int:
    """0 = healthy, 1 = render failed, 2 = a dependency is missing.

    Dependencies are checked *before* any directory is created, so a missing
    ffmpeg leaves no debris in the gallery.
    """
    print("manim-mcp self-test")
    print(f"  python      : {cfg.python}")
    print(f"  manim       : {cfg.manim or f'{cfg.python} -m manim'}")
    print(f"  ffmpeg      : {cfg.ffmpeg or '(missing)'}")
    print(f"  render root : {cfg.render_root}")

    problems = _dependency_problems(cfg)
    if problems:
        for problem in problems:
            print(f"  FAIL  {problem}")
        return 2

    font = style_mod.detect_cjk_font()
    print(f"  cjk font    : {font or '(none found; Chinese may render as boxes)'}")

    renderer = render_fn or render.render_scene
    try:
        paths = workspace.prepare_run(cfg.render_root, workspace.new_run_id())
        workspace.write_scene(
            paths, build_code() if build_code is not None else sample_scene(font)
        )
    except workspace.WorkspaceError as error:
        print(f"  FAIL  无法准备渲染目录：{error}")
        return 2

    outcome = renderer(cfg, paths, SAMPLE_SCENE_CLASS, "draft")

    if not outcome.ok or outcome.mp4 is None:
        diagnostic = outcome.diagnostic
        print("  FAIL  渲染未完成")
        if diagnostic is not None:
            print(f"        stage   : {diagnostic.stage}")
            print(f"        error   : {diagnostic.type}: {diagnostic.message}")
            if diagnostic.line:
                print(f"        line    : {diagnostic.line}")
            if diagnostic.hint:
                print(f"        hint    : {diagnostic.hint}")
        return 1

    print(f"  render      : OK in {outcome.seconds:.1f}s -> {outcome.mp4}")

    encoder = preview_fn or postprocess.build_preview
    preview = encoder(
        cfg.ffmpeg,
        outcome.mp4,
        paths.out,
        SAMPLE_SCENE_CLASS,
        target_bytes=cfg.gif_target_bytes,
        max_bytes=cfg.gif_max_bytes,
    )
    if preview.path is None:
        print("  preview     : 未生成（见上面的依赖问题）")
    else:
        print(f"  preview     : OK {preview.kind} {preview.byte_size} bytes -> {preview.path}")
        markdown = envelope.preview_markdown(preview.path)
        print(f"  markdown    : {markdown}")
    for note in preview.warnings:
        print(f"  warning     : {note}")

    print("  self-test PASSED")
    return 0
