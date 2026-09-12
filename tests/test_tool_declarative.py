"""Declarative tools compile a template, then hand off to the pipeline."""

from pathlib import Path

from manim_mcp.engine import workspace
from manim_mcp.tools import declarative
from tests.helpers import make_config, stub_preview, stub_render, text_of


def invoke(tmp_path: Path, template: str, **params):
    return declarative.run_template(
        make_config(tmp_path),
        template,
        quality=params.pop("quality", "draft"),
        title=params.pop("title", None),
        params=params,
        render_fn=stub_render(True),
        preview_fn=stub_preview(),
    )


def test_equation_produces_a_render_and_an_image_block(tmp_path: Path):
    blocks = invoke(tmp_path, "equation", steps=[r"a=b", r"a=c"])
    assert [block.type for block in blocks] == ["text", "image"]
    assert text_of(blocks)["sceneName"] == "EquationScene"


def test_each_template_reports_its_own_scene_class(tmp_path: Path):
    cases = {
        "equation": dict(steps=[r"a", r"b"]),
        "graph": dict(expressions=["x**2"]),
        "diagram": dict(nodes=[{"id": "a", "label": "甲"}], edges=[]),
        "compare": dict(
            left={"title": "甲", "items": ["1"]}, right={"title": "乙", "items": ["2"]}
        ),
    }
    expected = {
        "equation": "EquationScene",
        "graph": "GraphScene",
        "diagram": "DiagramScene",
        "compare": "CompareScene",
    }
    for template, params in cases.items():
        payload = text_of(invoke(tmp_path, template, **params))
        assert payload["sceneName"] == expected[template]


def test_generated_source_reaches_disk(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "equation", steps=[r"a=b", r"a=c"]))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    source = workspace.read_scene(paths)
    assert "class EquationScene(Scene):" in source
    assert '"a=c"' in source


def test_recorded_tool_name_is_the_template_name(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "graph", expressions=["x"]))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["tool"] == "graph"


def test_argument_summary_records_shapes_not_the_payload(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "equation", steps=[r"a", r"b", r"c"]))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"steps": 3}


def test_invalid_arguments_fail_before_any_run_directory_is_created(tmp_path: Path):
    blocks = invoke(tmp_path, "equation", steps=[r"only-one"])
    payload = text_of(blocks)
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert workspace.existing_run_ids(tmp_path) == []


def test_invalid_arguments_do_not_reach_the_renderer(tmp_path: Path):
    calls = []

    def spy_render(*args, **kwargs):
        calls.append(args)
        return stub_render(True)(*args, **kwargs)

    declarative.run_template(
        make_config(tmp_path), "graph", quality="draft", title=None,
        params={"expressions": []}, render_fn=spy_render, preview_fn=stub_preview(),
    )
    assert calls == []


def test_unknown_template_is_a_validate_failure(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "hologram"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert "hologram" in payload["error"]["message"]


def test_diagram_argument_summary_counts_nodes_and_edges(tmp_path: Path):
    payload = text_of(
        invoke(
            tmp_path,
            "diagram",
            nodes=[{"id": "a", "label": "甲"}, {"id": "b", "label": "乙"}],
            edges=[{"from": "a", "to": "b"}],
        )
    )
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"nodes": 2, "edges": 1}
