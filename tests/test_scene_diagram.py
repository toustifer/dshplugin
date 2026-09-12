"""Diagrams are node/edge graphs; validation must catch dangling references."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("diagram", **kwargs)


NODES = [
    {"id": "a", "label": "输入"},
    {"id": "b", "label": "处理"},
    {"id": "c", "label": "输出"},
]
EDGES = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]


def test_minimal_diagram_compiles():
    scene_class, code = build(nodes=NODES, edges=EDGES)
    assert scene_class == "DiagramScene"
    ast.parse(code)
    assert "输入" in code and "输出" in code


def test_node_order_is_preserved():
    _, code = build(nodes=NODES, edges=EDGES)
    assert code.index('"输入"') < code.index('"处理"') < code.index('"输出"')


def test_edge_referencing_an_unknown_node_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=NODES, edges=[{"from": "a", "to": "zzz"}])
    assert "zzz" in str(caught.value)


def test_duplicate_node_ids_are_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=[{"id": "a", "label": "x"}, {"id": "a", "label": "y"}], edges=[])
    assert "a" in str(caught.value)


def test_nodes_must_be_a_non_empty_list():
    with pytest.raises(SceneSpecError):
        build(nodes=[], edges=[])
    with pytest.raises(SceneSpecError):
        build(edges=[])


def test_node_needs_both_id_and_label():
    with pytest.raises(SceneSpecError):
        build(nodes=[{"id": "a"}], edges=[])
    with pytest.raises(SceneSpecError):
        build(nodes=[{"label": "x"}], edges=[])


def test_more_than_eight_nodes_is_rejected():
    many = [{"id": f"n{i}", "label": f"节点{i}"} for i in range(9)]
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=many, edges=[])
    assert "8" in str(caught.value)


def test_unknown_node_kind_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=[{"id": "a", "label": "x", "kind": "sparkle"}], edges=[])
    assert "sparkle" in str(caught.value)


def test_node_kind_defaults_to_process():
    _, code = build(nodes=[{"id": "a", "label": "x"}], edges=[])
    assert '("a", "x", "process")' in code


def test_each_kind_maps_to_its_declared_colour():
    _, code = build(
        nodes=[
            {"id": "a", "label": "p", "kind": "process"},
            {"id": "b", "label": "d", "kind": "decision"},
            {"id": "c", "label": "t", "kind": "terminal"},
            {"id": "d", "label": "g", "kind": "data"},
        ],
        edges=[],
    )
    ast.parse(code)
    assert "KIND_COLORS" in code


def test_edge_label_is_optional_and_emitted():
    _, code = build(nodes=NODES, edges=[{"from": "a", "to": "b", "label": "是"}])
    ast.parse(code)
    assert "是" in code


def test_horizontal_layout_is_emitted():
    _, code = build(nodes=NODES, edges=EDGES, layout="horizontal")
    ast.parse(code)
    assert 'LAYOUT = "horizontal"' in code


def test_vertical_layout_is_the_default():
    _, code = build(nodes=NODES, edges=EDGES)
    assert 'LAYOUT = "vertical"' in code


def test_unknown_layout_is_rejected():
    with pytest.raises(SceneSpecError):
        build(nodes=NODES, edges=EDGES, layout="diagonal")


def test_edges_must_be_a_list():
    with pytest.raises(SceneSpecError):
        build(nodes=NODES, edges="a->b")


def test_blank_node_label_is_rejected():
    with pytest.raises(SceneSpecError):
        build(nodes=[{"id": "a", "label": "   "}], edges=[])
