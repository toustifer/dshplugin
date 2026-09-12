"""Two columns, one contrast: the fastest way to make a difference legible."""

from __future__ import annotations

import json
from typing import Mapping

from ..style import preamble
from . import SceneSpecError

NAME = "compare"
SCENE_CLASS = "CompareScene"
SUMMARY = "左右对照，突出两种做法/两个概念的差异"
PARAMS = {
    "title": "可选，顶部标题",
    "left": "必填，{title, items}；items 为 1-5 条",
    "right": "必填，{title, items}；items 为 1-5 条",
    "left_color": "可选，red（默认）/ blue / green / highlight / grey",
    "right_color": "可选，green（默认）/ red / blue / highlight / grey",
    "cjk_font": "可选，中文字体名",
}

MAX_ITEMS = 5
COLORS = {
    "red": "C_RED",
    "blue": "C_BLUE",
    "green": "C_GREEN",
    "highlight": "C_HIGHLIGHT",
    "grey": "C_GREY",
}

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

TITLE = @@TITLE@@
LEFT_COLOR = @@LEFT_COLOR@@
RIGHT_COLOR = @@RIGHT_COLOR@@
LEFT_SIDE = (
    @@LEFT_TITLE@@,
    [
@@LEFT_ITEMS@@
    ],
)
RIGHT_SIDE = (
    @@RIGHT_TITLE@@,
    [
@@RIGHT_ITEMS@@
    ],
)


class CompareScene(Scene):
    def build_card(self, heading, items, accent):
        title = cn(heading, BODY_SIZE, accent)
        rows = VGroup(*[cn(item, NOTE_SIZE, WHITE) for item in items])
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        body = VGroup(title, rows).arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        frame = RoundedRectangle(
            corner_radius=0.18,
            width=max(4.3, body.width + 1.2),
            height=max(3.0, body.height + 1.0),
            color=accent,
            fill_opacity=0.10,
            stroke_width=2.5,
        )
        body.move_to(frame.get_center())
        return VGroup(frame, body)

    def construct(self):
        left_card = self.build_card(LEFT_SIDE[0], LEFT_SIDE[1], LEFT_COLOR)
        right_card = self.build_card(RIGHT_SIDE[0], RIGHT_SIDE[1], RIGHT_COLOR)
        cards = VGroup(left_card, right_card).arrange(RIGHT, buff=0.9)

        if TITLE:
            heading = cn(TITLE, TITLE_SIZE, WHITE).to_edge(UP, buff=0.7)
            cards.next_to(heading, DOWN, buff=0.6)
            self.play(Write(heading), run_time=0.8)

        self.play(FadeIn(left_card, shift=RIGHT * 0.4), run_time=1.0)
        self.play(FadeIn(right_card, shift=LEFT * 0.4), run_time=1.0)
        self.wait(TAIL_WAIT)
'''


def _literal(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _side(value, name: str) -> tuple[str, list[str]]:
    if value is None:
        raise SceneSpecError(f"compare: 缺少必填参数 {name}")
    if not isinstance(value, Mapping):
        raise SceneSpecError(f"compare: {name} 必须是对象 {{title, items}}")
    title = value.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SceneSpecError(f"compare: {name}.title 必须是非空字符串")
    items = value.get("items")
    if isinstance(items, str) or not isinstance(items, (list, tuple)):
        raise SceneSpecError(f"compare: {name}.items 必须是字符串数组")
    if not items:
        raise SceneSpecError(f"compare: {name}.items 至少需要一条")
    if len(items) > MAX_ITEMS:
        raise SceneSpecError(
            f"compare: {name}.items 最多 {MAX_ITEMS} 条，收到 {len(items)} 条"
        )
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise SceneSpecError(f"compare: {name}.items[{index}] 必须是非空字符串")
    return str(title), [str(item) for item in items]


def _color(value, default: str, name: str) -> str:
    if value is None:
        return COLORS[default]
    if not isinstance(value, str) or value not in COLORS:
        raise SceneSpecError(
            f"compare: {name} {value!r} 无效，可选 {', '.join(sorted(COLORS))}"
        )
    return COLORS[value]


def build(**kwargs) -> str:
    left_title, left_items = _side(kwargs.get("left"), "left")
    right_title, right_items = _side(kwargs.get("right"), "right")
    left_color = _color(kwargs.get("left_color"), "red", "left_color")
    right_color = _color(kwargs.get("right_color"), "green", "right_color")

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("compare: title 必须是字符串")

    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(kwargs.get("cjk_font")))
        .replace("@@TITLE@@", _literal(title or ""))
        .replace("@@LEFT_COLOR@@", left_color)
        .replace("@@RIGHT_COLOR@@", right_color)
        .replace("@@LEFT_TITLE@@", _literal(left_title))
        .replace("@@RIGHT_TITLE@@", _literal(right_title))
        .replace(
            "@@LEFT_ITEMS@@",
            "\n".join(f"        {_literal(item)}," for item in left_items),
        )
        .replace(
            "@@RIGHT_ITEMS@@",
            "\n".join(f"        {_literal(item)}," for item in right_items),
        )
    )
