"""Step-by-step LaTeX derivation — 3b1b's signature animation."""

from __future__ import annotations

import json
from typing import Sequence

from ..style import preamble
from . import SceneSpecError

NAME = "equation"
SCENE_CLASS = "EquationScene"
SUMMARY = "把一串 LaTeX 公式逐步变形，展示推导过程（2-6 步）"
PARAMS = {
    "title": "可选，顶部标题；中文会自动使用中文字体",
    "steps": "必填，2-6 个 LaTeX 字符串，每一步一个状态",
    "highlight": "可选，与 steps 等长的子串数组；每一步要高亮的 LaTeX 片段（必须是该步中真实存在的子串，否则静默不高亮）",
    "cjk_font": "可选，中文正文字体名；通常留空自动探测",
}

MIN_STEPS = 2
MAX_STEPS = 6

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

class EquationScene(Scene):
    def construct(self):
        steps = [
@@STEPS@@
        ]
        highlight = [
@@HIGHLIGHT@@
        ]
        HAS_TITLE = @@HAS_TITLE@@
        HAS_HIGHLIGHT = @@HAS_HIGHLIGHT@@

        expression = MathTex(steps[0])
        if HAS_HIGHLIGHT and highlight[0]:
            expression.set_color_by_tex(highlight[0], C_HIGHLIGHT)

        if HAS_TITLE:
            title = cn(@@TITLE@@, TITLE_SIZE, WHITE).to_edge(UP, buff=0.9)
            expression.next_to(title, DOWN, buff=0.7)
            self.play(Write(title), run_time=PLAY_RUN_TIME)

        self.play(Write(expression), run_time=PLAY_RUN_TIME)
        self.wait(TAIL_WAIT)

        for index in range(1, len(steps)):
            following = MathTex(steps[index])
            following.move_to(expression)
            if HAS_HIGHLIGHT and highlight[index]:
                following.set_color_by_tex(highlight[index], C_HIGHLIGHT)
            self.play(
                TransformMatchingTex(expression, following),
                run_time=PLAY_RUN_TIME * 1.2,
            )
            expression = following
            self.wait(TAIL_WAIT)

        if HAS_HIGHLIGHT and highlight[-1]:
            self.play(
                Indicate(expression, color=C_HIGHLIGHT, scale_factor=1.06),
                run_time=PLAY_RUN_TIME,
            )
'''


def _literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _arguments(**kwargs) -> tuple[str | None, Sequence[str], Sequence[str] | None, str | None]:
    steps = kwargs.get("steps")
    if steps is None:
        raise SceneSpecError("equation: 缺少必填参数 steps（2-6 个 LaTeX 字符串）")
    if isinstance(steps, str) or not isinstance(steps, (list, tuple)):
        raise SceneSpecError("equation: steps 必须是字符串数组，不能是单个字符串")
    if not (MIN_STEPS <= len(steps) <= MAX_STEPS):
        raise SceneSpecError(
            f"equation: steps 需要 {MIN_STEPS}-{MAX_STEPS} 步，收到 {len(steps)} 步"
        )
    for index, step in enumerate(steps):
        if not isinstance(step, str) or not step.strip():
            raise SceneSpecError(f"equation: steps[{index}] 必须是非空字符串")

    highlight = kwargs.get("highlight")
    if highlight is None:
        highlight = ["" for _ in steps]
    else:
        if isinstance(highlight, str) or not isinstance(highlight, (list, tuple)):
            raise SceneSpecError("equation: highlight 必须是字符串数组，与 steps 等长")
        if len(highlight) != len(steps):
            raise SceneSpecError(
                f"equation: highlight 长度 {len(highlight)} 与 steps 长度 {len(steps)} 不一致"
            )
        for index, item in enumerate(highlight):
            if not isinstance(item, str):
                raise SceneSpecError(f"equation: highlight[{index}] 必须是字符串")

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("equation: title 必须是字符串")

    return title, list(steps), list(highlight), kwargs.get("cjk_font")


def build(**kwargs) -> str:
    title, steps, highlight, cjk_font = _arguments(**kwargs)
    body = "\n".join(f"            {_literal(step)}," for step in steps)
    marks = "\n".join(f"            {_literal(mark)}," for mark in highlight)
    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(cjk_font))
        .replace("@@STEPS@@", body)
        .replace("@@HIGHLIGHT@@", marks)
        .replace("@@HAS_TITLE@@", "True" if title else "False")
        .replace("@@TITLE@@", _literal(title or ""))
        .replace("@@HAS_HIGHLIGHT@@", "True" if any(highlight) else "False")
    )
