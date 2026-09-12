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

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

LAYOUT = @@LAYOUT@@
TITLE = @@TITLE@@
BOX_HEIGHT = @@BOX_HEIGHT@@
ARROW_SEPARATION = @@ARROW_SEPARATION@@
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
            adjacent = abs(step) == 1
            skipping = abs(step) > 1
            forward = step > 0

            if LAYOUT == "horizontal":
                if adjacent:
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
                if adjacent:
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
                buff=0.18,
                color=C_EDGE,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.12,
            )
            arrows.add(arrow)
            if edge_label:
                tag = cn(edge_label, NOTE_SIZE - 6, C_HIGHLIGHT)
                # A label never uses the arrow's own centre: on a bowing edge that
                # centre is the empty middle of the curve, which is exactly where
                # the boxes it was routed around still are. Measured facts that
                # drive the placement below:
                #   * the straight adjacent arrow runs down the middle of the gap
                #     between two rows, so a tag anchored on the box centres lands
                #     on the nodes and on that line;
                #   * a handful of CJK glyphs is wider than the gap between two
                #     boxes, so the tag has to leave the column.
                # Hence: tags sit beside the column at a gap centre, or (for a
                # skipping edge) inside the gap, just off the bow.
                midpoint = (np.array(start) + np.array(end)) / 2
                if not adjacent:
                    # The row gap is the one band no box occupies: put the tag on
                    # its far side so neither border is touched.
                    gap_top = end_box.get_top()[1] if forward else start_box.get_top()[1]
                    gap_bottom = (
                        start_box.get_bottom()[1] if forward else end_box.get_bottom()[1]
                    )
                    if LAYOUT == "horizontal":
                        tag.move_to([midpoint[0], (gap_top + gap_bottom) / 2, 0])
                        tag.shift(
                            UP * (tag.height / 2 + ARROW_SEPARATION)
                            if forward
                            else DOWN * (tag.height / 2 + ARROW_SEPARATION)
                        )
                    else:
                        column_edge = min(
                            start_box.get_left()[0], end_box.get_left()[0]
                        )
                        tag.move_to(
                            [
                                column_edge - ARROW_SEPARATION - tag.width / 2,
                                (gap_top + gap_bottom) / 2,
                                0,
                            ]
                        )
                        tag.shift(
                            RIGHT * (tag.width / 2 + ARROW_SEPARATION)
                            if forward
                            else UP * (tag.height / 2 + ARROW_SEPARATION)
                        )
                elif LAYOUT == "horizontal":
                    column_top = max(start_box.get_top()[1], end_box.get_top()[1])
                    column_bottom = min(
                        start_box.get_bottom()[1], end_box.get_bottom()[1]
                    )
                    gap_center = (
                        (column_top + end_box.get_top()[1]) / 2
                        if forward
                        else (column_bottom + end_box.get_bottom()[1]) / 2
                    )
                    tag.move_to([midpoint[0], gap_center, 0])
                    tag.shift(
                        UP * (tag.height / 2 + ARROW_SEPARATION)
                        if forward
                        else DOWN * (tag.height / 2 + ARROW_SEPARATION)
                    )
                elif forward:
                    # Just off the right of the box outline, so the tag touches
                    # neither the line running down the gap nor the box below.
                    edge_right = max(start_box.get_right()[0], end_box.get_right()[0])
                    tag.move_to(
                        [
                            edge_right + ARROW_SEPARATION + tag.width / 2,
                            (start_box.get_bottom()[1] + end_box.get_top()[1]) / 2,
                            0,
                        ]
                    )
                else:
                    # The same, mirrored: this is the loop edge running back up
                    # the column, and its tag cannot sit on the boxes it links.
                    edge_left = min(start_box.get_left()[0], end_box.get_left()[0])
                    tag.move_to(
                        [
                            edge_left - ARROW_SEPARATION - tag.width / 2,
                            (start_box.get_top()[1] + end_box.get_bottom()[1]) / 2,
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
        .replace(
            "@@NODES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in nodes),
        )
        .replace(
            "@@EDGES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in edges),
        )
    )
