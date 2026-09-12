"""The equation template is 3b1b's signature move; it must emit valid source."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("equation", **kwargs)


def test_minimal_two_step_scene_compiles():
    scene_class, code = build(steps=[r"a = b", r"a = c"])
    assert scene_class == "EquationScene"
    ast.parse(code)
    assert r'"a = c"' in code


def test_steps_are_emitted_as_python_string_literals():
    _, code = build(steps=[r"\frac{1}{2}", r"\frac{2}{4}"])
    ast.parse(code)
    assert r'"\\frac{1}{2}"' in code


def test_unicode_steps_survive_codegen():
    _, code = build(steps=["能量 = 质量", "E = mc^2"])
    ast.parse(code)
    assert "能量 = 质量" in code


def test_title_switches_on_the_title_block_with_the_cjk_helper():
    _, code = build(title="欧拉恒等式", steps=[r"e^{i\pi}", r"-1"])
    ast.parse(code)
    assert "cn(" in code
    assert "欧拉恒等式" in code
    assert "HAS_TITLE = True" in code


def test_absent_title_switches_the_block_off():
    _, code = build(steps=[r"a", r"b"])
    ast.parse(code)
    assert "HAS_TITLE = False" in code


def test_highlight_length_must_match_steps():
    with pytest.raises(SceneSpecError) as caught:
        build(steps=[r"a", r"b"], highlight=["a"])
    assert "highlight" in str(caught.value)


def test_highlight_is_applied_per_step():
    _, code = build(steps=[r"a = b", r"a = c"], highlight=["b", "c"])
    ast.parse(code)
    assert "HAS_HIGHLIGHT = True" in code
    assert "set_color_by_tex" in code


def test_single_step_is_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[r"a"])


def test_seven_steps_are_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[f"x_{i}" for i in range(7)])


def test_empty_step_is_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[r"a", "   "])


def test_non_string_step_is_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[r"a", 42])


def test_steps_must_be_a_sequence():
    with pytest.raises(SceneSpecError):
        build(steps="a=b")


def test_missing_steps_is_rejected():
    with pytest.raises(SceneSpecError):
        build()


def test_preamble_carries_the_palette_and_the_font():
    _, code = build(steps=[r"a", r"b"], cjk_font="SimHei")
    assert 'config.background_color = "#0E1116"' in code
    assert 'FONT_CJK = "SimHei"' in code
    assert "from manim import *" in code
