"""Every template is reachable by name and validates before it emits source."""

import ast

import pytest

from manim_mcp import scenes


def test_registry_exposes_exactly_the_four_templates():
    assert sorted(scenes.registry()) == ["compare", "diagram", "equation", "graph"]


def test_every_template_compiles_and_declares_a_scene_class():
    assert all(template.scene_class for template in scenes.registry().values())
    assert all(template.summary for template in scenes.registry().values())


def test_unknown_template_is_rejected():
    with pytest.raises(scenes.SceneSpecError) as caught:
        scenes.build("nope")
    assert "nope" in str(caught.value)
    assert "equation" in str(caught.value)


def test_build_returns_class_and_compilable_source():
    scene_class, code = scenes.build("equation", steps=[r"a=b", r"a=c"])
    assert scene_class == "EquationScene"
    ast.parse(code)


def test_build_rejects_bad_template_arguments():
    with pytest.raises(scenes.SceneSpecError):
        scenes.build("equation", steps=[r"a=b"])


def test_catalogue_is_serialisable_for_the_style_guide():
    catalogue = scenes.catalogue()
    assert isinstance(catalogue, list)
    assert {row["name"] for row in catalogue} == set(scenes.registry())
    assert all(isinstance(row["params"], dict) for row in catalogue)
