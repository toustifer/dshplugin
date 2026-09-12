"""Boxes and arrows: the shape of a process, a pipeline, or a hierarchy."""

from __future__ import annotations

import json
from typing import Mapping, Sequence

from ..style import preamble, python_literal
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
BOX_HEIGHT = 0.95
# Minimum gap left between a label and the arrow or box it sits next to.
ARROW_SEPARATION = 0.14
# Gap between two rows (or columns) of boxes. An adjacent edge is drawn inside it,
# so the gap must leave room for a shaft the reader can actually see: `Arrow`
# shortens BOTH ends by `ARROW_BUFF`, and the tip is clamped to
# `TIP_RATIO * length`, so a gap that is only just wider than the two buffers
# collapses the arrow into an invisible stub.
NODE_GAP = 0.62
ARROW_BUFF = 0.06
ARROW_TIP_LENGTH = 0.18
ARROW_TIP_RATIO = 0.35
# Shortest shaft that still reads as an arrow at 480p.
MIN_VISIBLE_SHAFT = 0.4

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

LAYOUT = @@LAYOUT@@
TITLE = @@TITLE@@
BOX_HEIGHT = @@BOX_HEIGHT@@
ARROW_SEPARATION = @@ARROW_SEPARATION@@
NODE_GAP = @@NODE_GAP@@
ARROW_BUFF = @@ARROW_BUFF@@
ARROW_TIP_LENGTH = @@ARROW_TIP_LENGTH@@
ARROW_TIP_RATIO = @@ARROW_TIP_RATIO@@
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


def label_width(text):
    """Box width sized by rendered text, not by character count.

    A CJK glyph is roughly twice as wide as a Latin one at the same nominal size,
    so a flat per-character estimate leaves Chinese labels touching the border.
    """
    wide = sum(1 for character in text if ord(character) > 0x2E80)
    narrow = len(text) - wide
    return max(2.6, 0.28 * narrow + 0.52 * wide + 0.95)


class DiagramScene(Scene):
    def construct(self):
        boxes = VGroup()
        index_of = {}
        for position, (node_id, label, kind) in enumerate(NODE_SPECS):
            box = RoundedRectangle(
                corner_radius=0.14,
                width=label_width(label),
                height=BOX_HEIGHT,
                color=KIND_COLORS[kind],
                fill_opacity=0.14,
                stroke_width=2.5,
            )
            caption = cn(label, NOTE_SIZE, WHITE)
            caption.move_to(box)
            boxes.add(VGroup(box, caption))
            index_of[node_id] = position

        if LAYOUT == "horizontal":
            boxes.arrange(RIGHT, buff=NODE_GAP)
        else:
            boxes.arrange(DOWN, buff=NODE_GAP)
        boxes.move_to(ORIGIN)

        if TITLE:
            title = cn(TITLE, TITLE_SIZE, WHITE).to_edge(UP, buff=0.6)
            boxes.scale_to_fit_height(min(boxes.height, 4.6))
            boxes.next_to(title, DOWN, buff=0.55)
            self.play(Write(title), run_time=0.8)

        arrows = VGroup()
        labels = VGroup()
        for source, target, edge_label in EDGE_SPECS:
            source_index = index_of[source]
            target_index = index_of[target]
            start_box = boxes[source_index][0]
            end_box = boxes[target_index][0]

            # Reading order runs top-to-bottom (or left-to-right). Only a hop
            # between *neighbours* can be a straight arrow anchored on the facing
            # box edges. Any edge that skips over at least one node — in either
            # direction — would be drawn straight through the box in between, so
            # it leaves the column instead. Node order, not edge direction, is
            # what decides this: `check` -> `out` moves forward and still crosses
            # `recurse`, so "backwards" was the wrong question to ask.
            step = target_index - source_index
            # Only a single *forward* hop is drawn straight, inside the row gap.
            # Everything else leaves the column: a backward hop sharing that line
            # with its own forward twin reads as one double-headed arrow, and a hop
            # that skips a row would be drawn across the box in between.
            straight = step == 1
            skipping = abs(step) > 1
            forward = step > 0

            if LAYOUT == "horizontal":
                if straight:
                    if forward:
                        start = start_box.get_right()
                        end = end_box.get_left()
                    else:
                        start = start_box.get_left()
                        end = end_box.get_right()
                    arc = 0.0
                elif skipping and forward:
                    start = start_box.get_top() + UP * 0.55
                    end = end_box.get_top() + UP * 0.55
                    arc = 1.6
                elif skipping:
                    start = start_box.get_bottom() + DOWN * 0.55
                    end = end_box.get_bottom() + DOWN * 0.55
                    arc = -1.6
                else:  # the same node twice: a self-loop, handled by the skipping path
                    start = start_box.get_right()
                    end = end_box.get_right()
                    arc = 0.0
            else:
                if straight:
                    if forward:
                        start = start_box.get_bottom()
                        end = end_box.get_top()
                    else:
                        start = start_box.get_top()
                        end = end_box.get_bottom()
                    arc = 0.0
                elif skipping and forward:
                    start = start_box.get_right() + RIGHT * 0.6
                    end = end_box.get_right() + RIGHT * 0.6
                    arc = 1.6
                elif skipping:
                    start = start_box.get_left() + LEFT * 0.6
                    end = end_box.get_left() + LEFT * 0.6
                    arc = -1.6
                else:
                    start = start_box.get_right()
                    end = end_box.get_right()
                    arc = 0.0

            arrow = Arrow(
                start,
                end,
                path_arc=arc,
                buff=ARROW_BUFF,
                color=C_EDGE,
                stroke_width=3,
                tip_length=ARROW_TIP_LENGTH,
                max_tip_length_to_length_ratio=ARROW_TIP_RATIO,
            )
            arrows.add(arrow)
            if edge_label:
                tag = cn(edge_label, NOTE_SIZE - 6, C_HIGHLIGHT)
                # Anchor on the arrow's own path rather than on the boxes. The apex
                # of a bow is `point_from_proportion(0.5)`; `get_center()` is the
                # midpoint of the *chord*, which for a bowed edge is back on the
                # column, on top of the very boxes the edge was routed around.
                #
                # The side must be the direction the edge actually leaves the
                # column, which is not the same as `forward`: an adjacent forward
                # hop is straight, a skipping forward hop bows right, and both
                # backward shapes bow left. Choosing by `forward` alone is what put
                # a decision's "yes" tag on its "no" branch.
                apex = arrow.point_from_proportion(0.5)
                if LAYOUT == "horizontal":
                    tag.next_to(apex, UP if forward else DOWN, buff=ARROW_SEPARATION)
                elif straight or forward:
                    tag.next_to(apex, RIGHT, buff=ARROW_SEPARATION)
                else:
                    # A bow's apex is only ~0.3 units clear of the column, which is
                    # not enough for a four-character CJK label, so the tag is hung
                    # off the column's own outline at the apex's height instead.
                    column_left = min(
                        start_box.get_left()[0], end_box.get_left()[0]
                    )
                    tag.move_to(
                        [
                            column_left - ARROW_SEPARATION - tag.width / 2,
                            apex[1],
                            0,
                        ]
                    )
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
    """Route every literal through the shared helper.

    `json.dumps` was used here first and emitted `null` for an unlabelled edge
    (the label is legitimately absent), which parses cleanly and then dies with
    `NameError: name 'null' is not defined` the moment Manim imports the file.
    """
    return python_literal(value)


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


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
        .replace("@@BOX_HEIGHT@@", _number(BOX_HEIGHT))
        .replace("@@ARROW_SEPARATION@@", _number(ARROW_SEPARATION))
        .replace("@@NODE_GAP@@", _number(NODE_GAP))
        .replace("@@ARROW_BUFF@@", _number(ARROW_BUFF))
        .replace("@@ARROW_TIP_LENGTH@@", _number(ARROW_TIP_LENGTH))
        .replace("@@ARROW_TIP_RATIO@@", _number(ARROW_TIP_RATIO))
        .replace(
            "@@NODES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in nodes),
        )
        .replace(
            "@@EDGES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in edges),
        )
    )
