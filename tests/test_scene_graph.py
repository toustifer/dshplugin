"""Graphs are where expressions are evaluated, so injection safety matters."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("graph", **kwargs)


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
