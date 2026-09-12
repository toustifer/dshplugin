"""Cross-template code-generation invariants.

These guard the boundary between "text that parses" and "text that runs": Python's
parser accepts `null`, `true`, and `false` as ordinary identifiers, so an
`ast.parse` assertion cannot see a JSON literal that will raise `NameError` the
moment Manim imports the file. Only executing (or explicitly hunting for those
names) catches it — and a real render is too slow to run on every edit.
"""

import ast

import pytest

from manim_mcp import scenes

# Representative arguments per template, deliberately including optional fields
# that may legitimately be absent (an unlabelled edge is the case that broke).
CASES = {
    "equation": dict(steps=[r"a = b", r"a = c"]),
    "graph": dict(expressions=["x**2"]),
    "diagram": dict(
        nodes=[
            {"id": "a", "label": "甲"},
            {"id": "b", "label": "乙", "kind": "terminal"},
        ],
        edges=[{"from": "a", "to": "b"}],
    ),
    "compare": dict(
        left={"title": "甲", "items": ["1"]},
        right={"title": "乙", "items": ["2"]},
    ),
}

JSON_ONLY_TOKENS = {"null", "true", "false"}


def build(template: str, **overrides) -> str:
    params = dict(CASES[template])
    params.update(overrides)
    _, code = scenes.build(template, **params)
    return code


@pytest.mark.parametrize("template", sorted(CASES))
def test_generated_source_contains_no_json_only_tokens(template: str):
    """`null` parses fine and then dies at import; hunt for the names explicitly."""
    tree = ast.parse(build(template))
    offenders = sorted(
        {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in JSON_ONLY_TOKENS
        }
    )
    assert offenders == [], (
        f"{template} emitted JSON-only token(s) {offenders}; "
        "the generated file imports but raises NameError"
    )


def test_unlabelled_edge_emits_python_none():
    code = build("diagram", edges=[{"from": "a", "to": "b"}])
    assert '("a", "b", None)' in code


def test_labelled_edge_keeps_its_label():
    code = build("diagram", edges=[{"from": "a", "to": "b", "label": "是"}])
    assert '("a", "b", "是")' in code


def test_python_literal_never_emits_json_tokens():
    """The shared helper is the single place this class of bug can live."""
    from manim_mcp.style import python_literal

    assert python_literal(None) == "None"
    assert python_literal(True) == "True"
    assert python_literal(False) == "False"
    assert python_literal("是") == '"是"'
    assert python_literal([1.0, 2]) == "[1.0, 2]"


def test_cyclic_diagram_routes_back_edges_around_the_column():
    """A straight centre-to-centre arrow ploughs through every box it passes.

    The diagram template exists to make a process legible, so an edge that is not
    between neighbours has to leave the column: adjacent edges anchor on the
    facing box edges, skipping edges bow out to the side.
    """
    code = build("diagram", edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "a"}])
    ast.parse(code)
    assert "path_arc" in code
    assert "get_bottom" in code  # adjacent forward edge anchors on box edges
    assert "get_left" in code  # skipping edge bows out around the side
    assert "abs(step) == 1" in code
    assert "abs(step) > 1" in code


def test_skipping_forward_edge_bows_out_instead_of_going_straight():
    """`check`(2) -> `out`(4) has `recurse`(3) between it: a straight arrow crosses it.

    Index order alone is not enough — the old `target_index <= source_index` test
    called this edge "forward" and drew it through the box in between.
    """
    code = build(
        "diagram",
        nodes=[{"id": f"n{i}", "label": f"节点{i}"} for i in range(5)],
        edges=[{"from": "n2", "to": "n4", "label": "否"}],
    )
    # Forward skip: bow right with a positive arc, anchor off the right edge.
    ast.parse(code)
    assert "step = target_index - source_index" in code
    assert "abs(step) == 1" in code
    assert "abs(step) > 1" in code
    assert "start_box.get_right() + RIGHT * 0.6" in code
    assert "end_box.get_right() + RIGHT * 0.6" in code
    assert "arc = 1.6" in code
    # A single-node hop is still the straight, facing-edge arrow.
    assert "start_box.get_bottom()" in code
    assert "end_box.get_top()" in code
    assert "arc = 0.0" in code


def test_skipping_backward_edge_bows_out_the_other_side():
    code = build(
        "diagram",
        nodes=[{"id": f"n{i}", "label": f"节点{i}"} for i in range(4)],
        edges=[{"from": "n3", "to": "n0", "label": "回到判定"}],
    )
    ast.parse(code)
    assert "start_box.get_left() + LEFT * 0.6" in code
    assert "arc = -1.6" in code
    # The tag leaves the column rather than sitting on the boxes it passes.
    assert "edge_right + ARROW_SEPARATION + tag.width / 2" in code
    assert "edge_left - ARROW_SEPARATION - tag.width / 2" in code


def test_horizontal_layout_bows_skipping_edges_over_and_under_the_row():
    code = build(
        "diagram",
        layout="horizontal",
        edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    )
    ast.parse(code)
    assert "start_box.get_right()" in code
    assert "end_box.get_left()" in code
    assert "start_box.get_top() + UP *" in code
    assert "start_box.get_bottom() + DOWN *" in code


def test_diagram_edges_use_the_readable_edge_colour():
    """C_GREY on the #0E1116 background is nearly invisible for a thin arrow."""
    code = build("diagram", edges=[{"from": "a", "to": "b"}])
    ast.parse(code)
    assert 'C_EDGE = "#8A94A6"' in code
    arrow_call = code.split("arrow = Arrow(", 1)[1].split(")", 1)[0]
    assert "color=C_EDGE" in arrow_call
    assert "C_GREY" not in arrow_call


def test_diagram_labels_clear_the_nodes_and_the_arc_they_annotate():
    """A bowing arrow leaves the column, so its label has to follow it out.

    Anchoring the tag at `arrow.get_center() + LEFT * 0.95` puts a long CJK label
    straight back over the boxes the arc was routed around, and the arrow centre
    on a bowing edge is precisely the empty middle of the curve. A tag anchored on
    the box centres instead lands on the node text itself.
    """
    code = build("diagram", edges=[{"from": "a", "to": "b", "label": "是"}])
    ast.parse(code)
    assert "arrow.get_center()" not in code
    assert "ARROW_SEPARATION = 0.14" in code
    # A tag never uses the box centres or the arrow centre: it is placed from the
    # box outline and its own width instead.
    assert "tag.width / 2" in code and "tag.height / 2" in code
    assert "edge_right + ARROW_SEPARATION + tag.width / 2" in code
    assert "edge_left - ARROW_SEPARATION - tag.width / 2" in code
    assert "start_box.get_bottom()[1] + end_box.get_top()[1]" in code


def test_skipping_edge_label_goes_into_the_row_gap():
    """A tag is wider than the gap between two boxes, so it sits in a row gap."""
    code = build(
        "diagram",
        nodes=[
            {"id": "a", "label": "甲"},
            {"id": "b", "label": "乙"},
            {"id": "c", "label": "丙"},
        ],
        edges=[{"from": "a", "to": "c", "label": "否"}],
    )
    ast.parse(code)
    assert "end_box.get_top()[1] if forward else start_box.get_top()[1]" in code
    assert "start_box.get_bottom()[1] if forward else end_box.get_bottom()[1]" in code


def test_diagram_edges_keep_a_visible_gap_from_the_boxes():
    code = build("diagram", edges=[{"from": "a", "to": "b"}])
    assert "buff=0.18" in code


def test_diagram_sizes_boxes_by_rendered_text_width():
    """A CJK glyph is about twice as wide as a Latin one at the same size."""
    code = build("diagram")
    tree = ast.parse(code)
    source = next(
        (
            ast.get_source_segment(code, node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "label_width"
        ),
        None,
    )
    assert source is not None, "diagram must size boxes by rendered text width, not char count"

    namespace: dict = {}
    exec(source, namespace)  # noqa: S102 - running the emitted helper is the assertion
    label_width = namespace["label_width"]

    # Four CJK characters must ask for a wider box than eight Latin ones.
    assert label_width("递归处理两侧") > label_width("abcdefgh")
    assert label_width("ab") >= 2.6  # never narrower than the floor
