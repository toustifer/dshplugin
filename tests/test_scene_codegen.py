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

    The diagram template exists to make a process legible, so a loop edge has to
    leave the column: forward edges anchor on the facing box edges, back edges
    bow out to the side.
    """
    code = build("diagram", edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "a"}])
    ast.parse(code)
    assert "path_arc" in code
    assert "get_bottom" in code  # forward edge anchors on box edges
    assert "get_left" in code  # back edge bows out around the side
    assert "backwards" in code


def test_acyclic_diagram_still_emits_the_same_routing_code():
    """Routing is decided at render time from node order, not baked per edge."""
    code = build("diagram", edges=[{"from": "a", "to": "b"}])
    ast.parse(code)
    assert "backwards = target_index <= source_index" in code


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
