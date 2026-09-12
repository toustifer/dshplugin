"""Side-by-side comparison: the anti-pattern / pattern explainer."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("compare", **kwargs)


LEFT = {"title": "错误做法", "items": ["先写实现", "再补测试"]}
RIGHT = {"title": "推荐做法", "items": ["先写测试", "再写实现"]}


def test_minimal_comparison_compiles():
    scene_class, code = build(left=LEFT, right=RIGHT)
    assert scene_class == "CompareScene"
    ast.parse(code)
    assert "错误做法" in code
    assert "推荐做法" in code


def test_items_keep_their_order():
    _, code = build(left=LEFT, right=RIGHT)
    assert code.index("先写实现") < code.index("再补测试")
    assert code.index("先写测试") < code.index("再写实现")


def test_side_must_be_an_object():
    with pytest.raises(SceneSpecError):
        build(left="nope", right=RIGHT)


def test_side_requires_a_title():
    with pytest.raises(SceneSpecError):
        build(left={"items": ["a"]}, right=RIGHT)


def test_side_requires_at_least_one_item():
    with pytest.raises(SceneSpecError):
        build(left={"title": "x", "items": []}, right=RIGHT)


def test_more_than_five_items_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(left={"title": "x", "items": [f"i{i}" for i in range(6)]}, right=RIGHT)
    assert "5" in str(caught.value)


def test_blank_item_is_rejected():
    with pytest.raises(SceneSpecError):
        build(left={"title": "x", "items": ["ok", "  "]}, right=RIGHT)


def test_missing_left_is_rejected():
    with pytest.raises(SceneSpecError):
        build(right=RIGHT)


def test_title_is_optional_but_emitted_when_present():
    _, with_title = build(left=LEFT, right=RIGHT, title="两种顺序")
    _, without_title = build(left=LEFT, right=RIGHT)
    assert 'TITLE = "两种顺序"' in with_title
    assert 'TITLE = ""' in without_title


def test_left_and_right_use_distinct_accent_colours():
    _, code = build(left=LEFT, right=RIGHT)
    ast.parse(code)
    assert "LEFT_COLOR = C_RED" in code
    assert "RIGHT_COLOR = C_GREEN" in code


def test_custom_colours_are_honoured():
    _, code = build(left=LEFT, right=RIGHT, left_color="blue", right_color="grey")
    assert "LEFT_COLOR = C_BLUE" in code
    assert "RIGHT_COLOR = C_GREY" in code


def test_unknown_colour_name_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(left=LEFT, right=RIGHT, left_color="chartreuse")
    assert "chartreuse" in str(caught.value)
