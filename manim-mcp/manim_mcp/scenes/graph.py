"""Function plots with optional tangent, area fill, and a live parameter.

Expressions travel as *strings* and are evaluated with an explicit namespace. That
keeps codegen safe (no quoting or escaping of model text into source) and makes the
animated-parameter case fall out for free: the tracker's value is simply rebound in
the namespace on every frame.
"""

from __future__ import annotations

import json
import re
from typing import Mapping, Sequence

from ..style import preamble
from . import SceneSpecError

NAME = "graph"
SCENE_CLASS = "GraphScene"
SUMMARY = "函数图像，可叠加切线、面积填充与参数滑动"
PARAMS = {
    "title": "可选，顶部标题",
    "expressions": "必填，1-3 个 Python 表达式字符串，变量是 x，可用 np.*",
    "x_range": "可选，[起, 止, 步长]，默认 [-4, 4, 1]",
    "y_range": "可选，[起, 止, 步长]，默认 [-3, 3, 1]",
    "highlight": "可选，{x: 数值, tangent: 布尔, area: [a, b]}；x 必填",
    "parameter": "可选，{symbol: 标识符, from: 数值, to: 数值}；表达式中出现该符号即可动态变化",
    "cjk_font": "可选，中文字体名",
}

DEFAULT_X_RANGE = (-4.0, 4.0, 1.0)
DEFAULT_Y_RANGE = (-3.0, 3.0, 1.0)
MAX_EXPRESSIONS = 3
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TEMPLATE = '''from manim import *
import numpy as np

@@PREAMBLE@@

X_RANGE = @@X_RANGE@@
Y_RANGE = @@Y_RANGE@@
EXPRESSIONS = [
@@EXPRESSIONS@@
]
HAS_TITLE = @@HAS_TITLE@@
HIGHLIGHT_X = @@HIGHLIGHT_X@@
SHOW_TANGENT = @@SHOW_TANGENT@@
SHOW_AREA = @@SHOW_AREA@@
AREA_RANGE = @@AREA_RANGE@@
HAS_PARAMETER = @@HAS_PARAMETER@@
PARAM_SYMBOL = @@PARAM_SYMBOL@@
PARAM_FROM = @@PARAM_FROM@@
PARAM_TO = @@PARAM_TO@@
PLOT_COLORS = [C_BLUE, C_GREEN, C_RED]


def evaluate(expression, x, bindings):
    namespace = {"np": np, "x": x}
    namespace.update(bindings)
    return eval(expression, {"__builtins__": {}}, namespace)


def visible_bounds(expression, bindings, samples=400):
    """The stretch of X_RANGE where the curve is still inside Y_RANGE.

    `Axes.plot` does not clip to `y_range`: x**2 on [-4, 4] leaves the window at
    |x| = sqrt(3) and the rest of the parabola is drawn across the title. Sampling
    the curve and shrinking the drawn interval is the only way to keep it in frame.
    The full range comes back when nothing is visible, so a curve that is entirely
    off-screen still renders (as nothing) instead of raising.
    """
    low = X_RANGE[0]
    high = X_RANGE[1]
    visible_low = None
    visible_high = None
    for index in range(samples):
        x = X_RANGE[0] + (X_RANGE[1] - X_RANGE[0]) * index / (samples - 1)
        try:
            y = evaluate(expression, x, bindings)
        except Exception:
            # Model text is arbitrary; one bad sample must not kill the render.
            continue
        if y is None or y != y:
            continue
        if Y_RANGE[0] <= y <= Y_RANGE[1]:
            if visible_low is None:
                visible_low = x
            visible_high = x
    if visible_low is None:
        return low, high
    return visible_low, visible_high


class GraphScene(Scene):
    def construct(self):
        axes = Axes(
            x_range=X_RANGE,
            y_range=Y_RANGE,
            x_length=9.5,
            y_length=5.0,
            axis_config={"color": C_GREY, "include_numbers": True, "font_size": 22},
            tips=False,
        )
        labels = axes.get_axis_labels(MathTex("x"), MathTex("y"))

        if HAS_TITLE:
            # `get_axis_labels` puts the y label at the very top of the y axis,
            # which is exactly the band the title occupies. Moving the axes (and
            # their labels with them) before anything is plotted keeps the two
            # apart, and `axes.c2p` follows the shift so every curve, dot, and
            # fill stays glued to the axes.
            axes.shift(DOWN * 0.55)
            labels.shift(DOWN * 0.55)

        self.play(Create(axes), Write(labels), run_time=1.0)

        if HAS_TITLE:
            title = cn(@@TITLE@@, TITLE_SIZE, WHITE).to_edge(UP, buff=0.45)
            self.play(Write(title), run_time=0.8)

        if HAS_PARAMETER:
            tracker = ValueTracker(PARAM_FROM)
            graphs = [
                always_redraw(
                    lambda expression=expression, color=color: axes.plot(
                        lambda x: evaluate(
                            expression, x, {PARAM_SYMBOL: tracker.get_value()}
                        ),
                        x_range=visible_bounds(
                            expression, {PARAM_SYMBOL: tracker.get_value()}
                        ),
                        color=color,
                    )
                )
                for expression, color in zip(EXPRESSIONS, PLOT_COLORS)
            ]
            self.add(*graphs)
            self.play(
                tracker.animate.set_value(PARAM_TO),
                run_time=3.0,
                rate_func=linear,
            )
        else:
            graphs = [
                axes.plot(
                    lambda x, expression=expression: evaluate(expression, x, {}),
                    x_range=visible_bounds(EXPRESSIONS[i], {}),
                    color=color,
                )
                for i, (expression, color) in enumerate(zip(EXPRESSIONS, PLOT_COLORS))
            ]
            for graph in graphs:
                self.play(Create(graph), run_time=1.2)
                self.wait(0.3)

        primary = graphs[0]
        if HIGHLIGHT_X is not None:
            point = Dot(
                axes.c2p(HIGHLIGHT_X, evaluate(EXPRESSIONS[0], HIGHLIGHT_X, {})),
                color=C_HIGHLIGHT,
            )
            self.play(FadeIn(point, scale=0.6), run_time=0.6)

            if SHOW_TANGENT:
                slope_group = axes.get_secant_slope_group(
                    x=HIGHLIGHT_X,
                    graph=primary,
                    dx=0.01,
                    dx_line_color=C_HIGHLIGHT,
                    dy_line_color=C_HIGHLIGHT,
                    secant_line_color=C_HIGHLIGHT,
                    secant_line_length=3.5,
                )
                self.play(Create(slope_group), run_time=1.0)

            if SHOW_AREA:
                # The fill is clipped by the same y_range, so it overflows the
                # frame in exactly the same places the curve does. Intersect the
                # requested interval with the curve's visible window first.
                area_low, area_high = visible_bounds(EXPRESSIONS[0], {})
                area_low = max(AREA_RANGE[0], area_low)
                area_high = min(AREA_RANGE[1], area_high)
                if area_low < area_high:
                    area = axes.get_area(
                        primary,
                        x_range=[area_low, area_high],
                        color=C_HIGHLIGHT,
                        opacity=0.35,
                    )
                    self.play(FadeIn(area), run_time=1.0)

        self.wait(TAIL_WAIT)
'''


def _literal(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _number(value: float) -> str:
    """Render an integral float as an int, so [-4.0, 4.0, 1.0] reads as [-4, 4, 1]."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _range_literal(values: Sequence[float]) -> str:
    return "[" + ", ".join(_number(item) for item in values) + "]"


def _range(value, default, label: str) -> tuple[float, float, float]:
    if value is None:
        return default
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or len(value) != 3:
        raise SceneSpecError(f"graph: {label} 必须是 [起, 止, 步长] 三个数")
    numbers: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise SceneSpecError(f"graph: {label}[{index}] 必须是数字")
        numbers.append(float(item))
    start, stop, step = numbers
    if start >= stop:
        raise SceneSpecError(f"graph: {label} 的起始值必须小于终止值")
    if step <= 0:
        raise SceneSpecError(f"graph: {label} 的步长必须为正数")
    return start, stop, step


def _expressions(value) -> list[str]:
    if value is None:
        raise SceneSpecError("graph: 缺少必填参数 expressions（1-3 个表达式字符串）")
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise SceneSpecError("graph: expressions 必须是字符串数组")
    if not value:
        raise SceneSpecError("graph: expressions 至少需要一个表达式")
    if len(value) > MAX_EXPRESSIONS:
        raise SceneSpecError(
            f"graph: expressions 最多 {MAX_EXPRESSIONS} 条，收到 {len(value)} 条"
        )
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise SceneSpecError(f"graph: expressions[{index}] 必须是非空字符串")
    return [str(item) for item in value]


def _highlight(value) -> tuple[float | None, bool, bool, tuple[float, float] | None]:
    if value is None:
        return None, False, False, None
    if not isinstance(value, Mapping):
        raise SceneSpecError("graph: highlight 必须是对象 {x, tangent, area}")

    point = value.get("x")
    if point is None:
        raise SceneSpecError("graph: highlight 缺少必填的 x")
    if isinstance(point, bool) or not isinstance(point, (int, float)):
        raise SceneSpecError("graph: highlight.x 必须是数字")
    point = float(point)

    tangent = bool(value.get("tangent", False))
    area_raw = value.get("area")
    if area_raw is None or area_raw is False:
        return point, tangent, False, None
    if area_raw is True:
        return point, tangent, True, (point - 1.0, point + 1.0)
    if isinstance(area_raw, str) or not isinstance(area_raw, (list, tuple)) or len(area_raw) != 2:
        raise SceneSpecError("graph: highlight.area 必须是 [a, b] 或 true")
    left, right = area_raw
    for index, item in enumerate((left, right)):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise SceneSpecError(f"graph: highlight.area[{index}] 必须是数字")
    if float(left) >= float(right):
        raise SceneSpecError("graph: highlight.area 的起点必须小于终点")
    return point, tangent, True, (float(left), float(right))


def _parameter(value) -> tuple[str, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise SceneSpecError("graph: parameter 必须是对象 {symbol, from, to}")
    symbol = value.get("symbol")
    if not isinstance(symbol, str) or not IDENTIFIER_RE.match(symbol):
        raise SceneSpecError(
            f"graph: parameter.symbol 必须是合法的 Python 标识符，收到 {symbol!r}"
        )
    start = value.get("from")
    stop = value.get("to")
    for name, item in (("from", start), ("to", stop)):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise SceneSpecError(f"graph: parameter.{name} 必须是数字")
    if float(start) == float(stop):
        raise SceneSpecError("graph: parameter 的 from 与 to 不能相同，否则动画没有变化")
    return symbol, float(start), float(stop)


def build(**kwargs) -> str:
    expressions = _expressions(kwargs.get("expressions"))
    x_range = _range(kwargs.get("x_range"), DEFAULT_X_RANGE, "x_range")
    y_range = _range(kwargs.get("y_range"), DEFAULT_Y_RANGE, "y_range")
    point, tangent, area, area_range = _highlight(kwargs.get("highlight"))
    parameter = _parameter(kwargs.get("parameter"))

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("graph: title 必须是字符串")

    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(kwargs.get("cjk_font")))
        .replace("@@X_RANGE@@", _range_literal(x_range))
        .replace("@@Y_RANGE@@", _range_literal(y_range))
        .replace("@@EXPRESSIONS@@", "\n".join(f"    {_literal(e)}," for e in expressions))
        .replace("@@HAS_TITLE@@", "True" if title else "False")
        .replace("@@TITLE@@", _literal(title or ""))
        .replace("@@HIGHLIGHT_X@@", "None" if point is None else repr(point))
        .replace("@@SHOW_TANGENT@@", "True" if tangent else "False")
        .replace("@@SHOW_AREA@@", "True" if area else "False")
        .replace("@@AREA_RANGE@@", "None" if area_range is None else _range_literal(area_range))
        .replace("@@HAS_PARAMETER@@", "True" if parameter else "False")
        .replace("@@PARAM_SYMBOL@@", _literal(parameter[0] if parameter else ""))
        .replace("@@PARAM_FROM@@", repr(parameter[1]) if parameter else "0.0")
        .replace("@@PARAM_TO@@", repr(parameter[2]) if parameter else "0.0")
    )
