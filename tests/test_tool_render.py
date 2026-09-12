"""The escape hatch: raw Manim code, with the same bookkeeping as any template."""

from pathlib import Path

from manim_mcp.engine import workspace
from manim_mcp.tools import render as render_tool
from tests.helpers import make_config, stub_preview, stub_render, text_of

GOOD = '''from manim import *


class Custom(Scene):
    def construct(self):
        self.play(Write(Text("hi")))
'''


def invoke(tmp_path: Path, code: str, scene_name=None, quality="draft"):
    return render_tool.run_code(
        make_config(tmp_path),
        code=code,
        scene_name=scene_name,
        quality=quality,
        render_fn=stub_render(True),
        preview_fn=stub_preview(),
    )


def test_valid_code_renders_and_infers_the_scene_class(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    assert payload["ok"] is True
    assert payload["sceneName"] == "Custom"


def test_explicit_scene_name_is_honoured(tmp_path: Path):
    code = GOOD + "\n\nclass Second(Scene):\n    def construct(self):\n        pass\n"
    payload = text_of(invoke(tmp_path, code, scene_name="Second"))
    assert payload["sceneName"] == "Second"


def test_unknown_scene_name_is_a_validate_failure(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD, scene_name="Absent"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert workspace.existing_run_ids(tmp_path) == []


def test_syntactically_broken_code_never_reaches_the_renderer(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "from manim import *\nclass X(Scene)\n    pass\n"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert workspace.existing_run_ids(tmp_path) == []


def test_missing_construct_never_reaches_the_renderer(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "from manim import *\n\nclass X(Scene):\n    pass\n"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"


def test_recorded_tool_name_is_render(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["tool"] == "render"


def test_argument_summary_records_the_line_count_not_the_source(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"lines": len(GOOD.splitlines())}
    assert "source" not in meta


def test_the_model_source_is_written_verbatim(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    assert workspace.read_scene(paths) == GOOD
