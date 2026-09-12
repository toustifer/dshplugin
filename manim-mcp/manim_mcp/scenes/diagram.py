"""Boxes and arrows: the shape of a process, a pipeline, or a hierarchy."""

from __future__ import annotations

import json
from typing import Mapping, Sequence

from ..style import preamble
from . import SceneSpecError

NAME = "diagram"
SCENE_CLASS = "DiagramScene"
SUMMARY = "流程 / 架构 / 因果关系的框图，节点 + 箭头"
PARAMS = {
    "title": "可选，顶部标题",
    "nodes": "必填，1-8 个 {id, label, kind}；kind 取 process/decision/terminal/data（只影响配色）",
    "edges": "必填，{from, to, label?} 数组；from/to 必须是已声明的 id",
    "layout": "可选，vertical（默认）或 horizontal",
    "cjk_font": "可选，中文字体名",
}

MAX_NODES = 8
KINDS = ("process", "decision", "terminal", "data")
LAYOUTS = ("vertical", "horizontal")

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

LAYOUT = @@LAYOUT@@
TITLE = @@TITLE@@
KIND_COLORS = {
    "process": C_BLUE,
    "decision": C_HIGHLIGHT,
    "terminal": C_GREEN,
    "data": C_GREY,
}
NODE_SPECS = [
@@NODES@@
]
EDGE_SPECS = [
@@EDGES@@
]


class DiagramScene(Scene):
    def construct(self):
        boxes = VGroup()
        index_of = {}
        for position, (node_id, label, kind) in enumerate(NODE_SPECS):
            box = RoundedRectangle(
                corner_radius=0.14,
                width=max(2.6, 0.34 * len(label) + 0.9),
                height=0.95,
                color=KIND_COLORS[kind],
                fill_opacity=0.14,
                stroke_width=2.5,
            )
            caption = cn(label, NOTE_SIZE, WHITE)
            caption.move_to(box)
            boxes.add(VGroup(box, caption))
            index_of[node_id] = position

        if LAYOUT == "horizontal":
            boxes.arrange(RIGHT, buff=1.1)
        else:
            boxes.arrange(DOWN, buff=0.55)
        boxes.move_to(ORIGIN)

        if TITLE:
            title = cn(TITLE, TITLE_SIZE, WHITE).to_edge(UP, buff=0.6)
            boxes.scale_to_fit_height(min(boxes.height, 4.6))
            boxes.next_to(title, DOWN, buff=0.55)
            self.play(Write(title), run_time=0.8)

        arrows = VGroup()
        labels = VGroup()
        for source, target, edge_label in EDGE_SPECS:
            start_box = boxes[index_of[source]][0]
            end_box = boxes[index_of[target]][0]
            arrow = Arrow(
                start_box.get_center(),
                end_box.get_center(),
                buff=0.62,
                color=C_GREY,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.12,
            )
            arrows.add(arrow)
            if edge_label:
                tag = cn(edge_label, NOTE_SIZE - 6, C_HIGHLIGHT)
                tag.move_to(arrow.get_center() + RIGHT * 0.42)
                labels.add(tag)

        self.play(
            LaggedStart(
                *[FadeIn(box, shift=RIGHT * 0.25) for box in boxes],
                lag_ratio=0.22,
            ),
            run_time=1.4,
        )
        if arrows:
            self.play(
                LaggedStart(*[GrowArrow(arrow) for arrow in arrows], lag_ratio=0.22),
                run_time=1.2,
            )
        if labels:
            self.play(FadeIn(labels), run_time=0.5)
        self.wait(TAIL_WAIT)
'''


def _literal(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _nodes(value) -> list[tuple[str, str, str]]:
    if value is None:
        raise SceneSpecError("diagram: 缺少必填参数 nodes")
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise SceneSpecError("diagram: nodes 必须是数组")
    if not value:
        raise SceneSpecError("diagram: nodes 至少需要一个节点")
    if len(value) > MAX_NODES:
        raise SceneSpecError(f"diagram: nodes 最多 {MAX_NODES} 个，收到 {len(value)} 个")

    parsed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for index, node in enumerate(value):
        if not isinstance(node, Mapping):
            raise SceneSpecError(f"diagram: nodes[{index}] 必须是对象 {{id, label, kind}}")
        node_id = node.get("id")
        label = node.get("label")
        if not isinstance(node_id, str) or not node_id.strip():
            raise SceneSpecError(f"diagram: nodes[{index}] 缺少非空的 id")
        if not isinstance(label, str) or not label.strip():
            raise SceneSpecError(f"diagram: nodes[{index}] 缺少非空的 label")
        if node_id in seen:
            raise SceneSpecError(f"diagram: 节点 id {node_id!r} 重复")
        seen.add(node_id)
        kind = node.get("kind", "process")
        if kind not in KINDS:
            raise SceneSpecError(
                f"diagram: 节点 {node_id!r} 的 kind {kind!r} 无效，可选 {', '.join(KINDS)}"
            )
        parsed.append((node_id, str(label), str(kind)))
    return parsed


def _edges(value, node_ids: set[str]) -> list[tuple[str, str, str | None]]:
    if value is None:
        raise SceneSpecError("diagram: 缺少必填参数 edges（可以为空数组）")
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise SceneSpecError("diagram: edges 必须是数组")

    parsed: list[tuple[str, str, str | None]] = []
    for index, edge in enumerate(value):
        if not isinstance(edge, Mapping):
            raise SceneSpecError(f"diagram: edges[{index}] 必须是对象 {{from, to, label?}}")
        source = edge.get("from")
        target = edge.get("to")
        for name, node_id in (("from", source), ("to", target)):
            if not isinstance(node_id, str) or not node_id.strip():
                raise SceneSpecError(f"diagram: edges[{index}].{name} 必须是非空字符串")
            if node_id not in node_ids:
                raise SceneSpecError(
                    f"diagram: edges[{index}].{name} 指向未声明的节点 {node_id!r}"
                )
        label = edge.get("label")
        if label is not None and not isinstance(label, str):
            raise SceneSpecError(f"diagram: edges[{index}].label 必须是字符串")
        parsed.append((str(source), str(target), label))
    return parsed


def build(**kwargs) -> str:
    nodes = _nodes(kwargs.get("nodes"))
    node_ids = {node[0] for node in nodes}
    edges = _edges(kwargs.get("edges"), node_ids)

    layout = kwargs.get("layout", "vertical")
    if layout not in LAYOUTS:
        raise SceneSpecError(
            f"diagram: layout {layout!r} 无效，可选 {', '.join(LAYOUTS)}"
        )

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("diagram: title 必须是字符串")

    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(kwargs.get("cjk_font")))
        .replace("@@LAYOUT@@", _literal(layout))
        .replace("@@TITLE@@", _literal(title or ""))
        .replace(
            "@@NODES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in nodes),
        )
        .replace(
            "@@EDGES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in edges),
        )
    )
