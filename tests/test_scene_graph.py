"""Graphs are where expressions are evaluated, so injection safety matters."""

import ast
import math

import numpy as np
import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError

# `Axes.plot` does not clip to `y_range`. With the default [-3, 3] window, `x**2`
# reaches y=16 at x=4 and the parabola is drawn straight up through the title, so
# the template has to shrink the drawn interval to where the curve is still on
# screen. `evaluate` is the only evaluator the template owns, so the bounds
# sampler has to be built out of it and can therefore be executed here.
SAMPLES = 400


def build(**kwargs):
    return scenes.build("graph", **kwargs)


def helper_source(code: str, name: str) -> str:
    """The verbatim source of one top-level function in the generated scene."""
    tree = ast.parse(code)
    source = next(
        (
            ast.get_source_segment(code, node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ),
        None,
    )
    assert source is not None, f"graph scene must define a module-level {name}()"
    return source


def run_visible_bounds(code: str, x_range, y_range, expression, bindings=None):
    """Execute the emitted `evaluate` + `visible_bounds` pair for real.

    The helper is the unit under test, and it is ordinary Python: exec'ing it with
    the graph constants bound by hand tests the actual behaviour instead of a
    string match.
    """
    namespace: dict = {"np": np}
    exec(  # noqa: S102 - running the emitted helper is the assertion
        "import numpy as np\n"
        f"X_RANGE = {list(x_range)}\n"
        f"Y_RANGE = {list(y_range)}\n\n"
        f"{helper_source(code, 'evaluate')}\n\n"
        f"{helper_source(code, 'visible_bounds')}\n",
        namespace,
    )
    return namespace["visible_bounds"](expression, dict(bindings or {}))


def test_minimal_plot_compiles():
    scene_class, code = build(expressions=["x**2"])
    assert scene_class == "GraphScene"
    ast.parse(code)
    assert "x**2" in code


def test_numpy_expression_keeps_its_module_reference():
    _, code = build(expressions=["np.sin(x)"])
    ast.parse(code)
    assert "import numpy as np" in code
    assert "np.sin(x)" in code


def test_expression_is_evaluated_not_inlined():
    """The expression travels as a string, so a stray quote cannot break codegen."""
    _, code = build(expressions=['x if x > 0 else "neg"'])
    ast.parse(code)
    assert 'x if x > 0 else \\"neg\\"' in code or 'x if x > 0 else "neg"' in code


def test_multiple_expressions_are_kept_in_order():
    _, code = build(expressions=["x", "x**2", "np.cos(x)"])
    ast.parse(code)
    assert code.index('"x"') < code.index('"x**2"') < code.index('"np.cos(x)"')


def test_more_than_three_expressions_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=["x", "x**2", "x**3", "x**4"])


def test_empty_expression_list_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=[])


def test_blank_expression_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=["x", "  "])


def test_expression_must_be_a_string():
    with pytest.raises(SceneSpecError):
        build(expressions=[42])


def test_missing_expressions_is_rejected():
    with pytest.raises(SceneSpecError):
        build()


def test_custom_x_range_is_emitted():
    _, code = build(expressions=["x"], x_range=[-2, 2, 1])
    ast.parse(code)
    assert "X_RANGE = [-2, 2, 1]" in code


def test_default_x_range_is_used_when_absent():
    _, code = build(expressions=["x"])
    assert "X_RANGE = [-4, 4, 1]" in code


def test_x_range_must_be_three_numbers():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], x_range=[0, 1])


def test_x_range_bounds_must_be_ordered():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], x_range=[4, -4, 1])


def test_x_range_step_must_be_positive():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], x_range=[0, 1, 0])


def test_highlight_point_adds_a_dot_and_a_tangent():
    _, code = build(expressions=["x**2"], highlight={"x": 1.0, "tangent": True})
    ast.parse(code)
    assert "HIGHLIGHT_X = 1.0" in code
    assert "SHOW_TANGENT = True" in code
    assert "get_secant_slope_group" in code


def test_highlight_area_uses_the_axis_fill_helper():
    _, code = build(expressions=["x**2"], highlight={"x": 1.0, "area": [0, 2]})
    ast.parse(code)
    assert "SHOW_AREA = True" in code
    assert "get_area" in code


def test_highlight_requires_x():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], highlight={"tangent": True})


def test_tangent_without_a_highlight_x_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], highlight={"tangent": True, "x": None})


def test_parameter_block_binds_the_symbol_through_eval():
    _, code = build(
        expressions=["a * np.sin(x)"],
        parameter={"symbol": "a", "from": 0.5, "to": 3.0},
    )
    ast.parse(code)
    assert 'PARAM_SYMBOL = "a"' in code
    assert "PARAM_FROM = 0.5" in code
    assert "PARAM_TO = 3.0" in code
    assert "eval(" in code
    assert "ValueTracker" in code


def test_parameter_symbol_must_be_a_python_identifier():
    with pytest.raises(SceneSpecError) as caught:
        build(expressions=["x"], parameter={"symbol": "a-b", "from": 0, "to": 1})
    assert "a-b" in str(caught.value)


def test_parameter_range_must_be_finite_numbers():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], parameter={"symbol": "a", "from": "0", "to": 1})


def test_parameter_from_and_to_must_differ():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], parameter={"symbol": "a", "from": 1, "to": 1})


def test_y_range_default_is_emitted():
    _, code = build(expressions=["x"])
    assert "Y_RANGE = [-3, 3, 1]" in code


def test_visible_bounds_helper_is_emitted_before_it_is_used():
    """`Axes.plot` ignores `y_range`, so the template needs its own clip window."""
    _, code = build(expressions=["x**2"])
    ast.parse(code)
    assert "def visible_bounds(" in code
    assert code.index("def visible_bounds(") < code.index("class GraphScene")


def test_visible_bounds_shrinks_x_squared_to_the_visible_window():
    """x**2 leaves y_range=[-3, 3] at |x| = sqrt(3); beyond that it is off-screen."""
    _, code = build(expressions=["x**2"])
    low, high = run_visible_bounds(code, [-4, 4, 1], [-3, 3, 1], "x**2")

    limit = math.sqrt(3.0) + 1e-6
    assert abs(low) <= limit, f"left bound {low} still draws the curve off-screen"
    assert abs(high) <= limit, f"right bound {high} still draws the curve off-screen"
    # The window is symmetric for an even function, so it must not be truncated.
    assert high - low > 2.0


def test_visible_bounds_falls_back_to_x_range_when_nothing_is_visible():
    _, code = build(expressions=["x**2 + 100"], y_range=[-3, 3, 1])
    assert run_visible_bounds(code, [-4, 4, 1], [-3, 3, 1], "x**2 + 100") == (-4.0, 4.0)


def test_visible_bounds_skips_points_where_the_expression_raises():
    """The evaluator is arbitrary model text, so one bad sample must not kill it."""
    _, code = build(expressions=["x"])
    low, high = run_visible_bounds(code, [-4, 4, 1], [-3, 3, 1], "1 / x")
    assert low >= -4.0 and high <= 4.0
    assert low < high


def test_each_curve_is_drawn_over_its_own_visible_bounds():
    _, code = build(expressions=["x", "x**2"])
    ast.parse(code)
    # The straight line needs the whole axis; x**2 must not inherit the same window,
    # so the window is indexed by the curve's position in EXPRESSIONS.
    assert "visible_bounds(EXPRESSIONS[i], {})" in code
    assert "enumerate(zip(EXPRESSIONS, PLOT_COLORS))" in code


def test_parameter_curves_recompute_bounds_from_the_tracker_each_frame():
    """A slider changes which x are on screen, so the clip window is per frame."""
    _, code = build(
        expressions=["a * np.sin(x)"],
        parameter={"symbol": "a", "from": 0.5, "to": 3.0},
    )
    ast.parse(code)
    assert "always_redraw" in code
    flat = " ".join(code.split())
    assert "visible_bounds( expression, {PARAM_SYMBOL: tracker.get_value()} )" in flat


def test_area_fill_is_clamped_to_the_curve_visible_bounds():
    """`get_area` fills over the same unclipped interval, so it overflows too."""
    _, code = build(
        expressions=["x**2"],
        highlight={"x": 1.0, "area": [0.0, 4.0]},
    )
    ast.parse(code)
    assert "SHOW_AREA = True" in code
    assert "visible_bounds" in code
    # The requested [0, 4] fill has to be intersected with the curve's window.
    assert "max(" in code and "min(" in code
    assert "AREA_RANGE" in code


def test_title_shifts_the_axes_and_labels_out_of_its_way():
    """The y label sits at the top of the y axis, level with the title band."""
    _, code = build(expressions=["x"], title="切线与面积")
    ast.parse(code)
    assert "DOWN * 0.55" in code
    # Ordering is the whole point: `axes.c2p` follows the shift only if the axes
    # moved before the curves were sampled from them.
    assert code.index("DOWN * 0.55") < code.index("graphs = [")
