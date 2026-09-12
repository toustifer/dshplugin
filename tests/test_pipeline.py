"""The one place where a render, a preview, and an index entry come together."""

from pathlib import Path

from manim_mcp.engine import index, workspace
from manim_mcp.engine.diagnostics import Diagnostic
from manim_mcp.tools import pipeline
from tests.helpers import make_config, stub_preview, stub_render, text_of

SCENE = (
    "from manim import *\n\n\n"
    "class EquationScene(Scene):\n"
    "    def construct(self):\n"
    "        pass\n"
)


def run(tmp_path: Path, **kwargs):
    cfg = kwargs.pop("cfg", None) or make_config(tmp_path)
    defaults = dict(
        tool_name="equation",
        title="欧拉恒等式",
        quality="draft",
        args_summary={"steps": 3},
        code=SCENE,
        scene_class="EquationScene",
        render_fn=stub_render(True),
        preview_fn=stub_preview(),
        run_id="20260912-153012-a1b2",
    )
    defaults.update(kwargs)
    return pipeline.execute(cfg, **defaults)


def test_success_creates_the_run_tree_and_two_blocks(tmp_path: Path):
    blocks = run(tmp_path)
    assert [block.type for block in blocks] == ["text", "image"]
    payload = text_of(blocks)
    assert payload["ok"] is True
    assert payload["runId"] == "20260912-153012-a1b2"
    assert payload["sceneName"] == "EquationScene"
    assert Path(payload["assets"]["mp4"]).exists()
    assert Path(payload["assets"]["preview"]).exists()


def test_success_preview_markdown_round_trips(tmp_path: Path):
    payload = text_of(run(tmp_path))
    markdown = payload["previewMarkdown"]
    assert markdown.startswith("![anim](/")
    assert markdown.endswith(".gif)")


def test_success_writes_run_json_and_index_adds_the_entry(tmp_path: Path):
    payload = text_of(run(tmp_path))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    meta = workspace.read_meta(paths)
    assert meta["status"] == "ok"
    assert meta["tool"] == "equation"
    assert meta["title"] == "欧拉恒等式"
    assert meta["sceneName"] == "EquationScene"

    entries = index.load_index(tmp_path)["runs"]
    assert [entry["runId"] for entry in entries] == [payload["runId"]]
    assert entries[0]["previewUrlPath"].endswith(".gif")


def test_success_records_the_argument_summary_not_the_source(tmp_path: Path):
    payload = text_of(run(tmp_path))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"steps": 3}
    assert "source" not in meta


def test_scene_source_is_written_to_disk(tmp_path: Path):
    payload = text_of(run(tmp_path))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    assert "EquationScene" in workspace.read_scene(paths)


def test_failure_returns_one_text_block_and_records_the_failure(tmp_path: Path):
    diagnostic = Diagnostic(
        stage="manim", type="NameError", message="name 'X' is not defined", line=4, hint="加 import"
    )
    blocks = run(tmp_path, render_fn=stub_render(False, diagnostic=diagnostic))
    assert [block.type for block in blocks] == ["text"]
    payload = text_of(blocks)
    assert payload["ok"] is False
    assert payload["stage"] == "manim"
    assert payload["error"]["type"] == "NameError"
    assert payload["hint"] == "加 import"
    assert Path(payload["codePath"]).exists()


def test_failure_still_lands_in_the_index_so_the_gallery_can_explain_it(tmp_path: Path):
    blocks = run(tmp_path, render_fn=stub_render(False))
    run_id = text_of(blocks)["runId"]
    entries = index.load_index(tmp_path)["runs"]
    assert entries[0]["runId"] == run_id
    assert entries[0]["status"] == "failed"


def test_missing_preview_degrades_to_text_only_with_a_warning(tmp_path: Path):
    blocks = run(tmp_path, preview_fn=stub_preview(None))
    assert [block.type for block in blocks] == ["text"]
    payload = text_of(blocks)
    assert payload["ok"] is True
    assert payload["previewMarkdown"] is None
    assert any("ffmpeg" in note for note in payload["warnings"])


def test_preview_path_with_markdown_breaking_characters_is_not_advertised(tmp_path: Path):
    cfg = make_config(tmp_path / "my (dir)")
    blocks = run(tmp_path, cfg=cfg)
    assert text_of(blocks)["previewMarkdown"] is None


def test_pruning_runs_after_a_successful_render(tmp_path: Path):
    cfg = make_config(tmp_path, keep_runs=1)
    for run_id in ("20260912-100000-0001", "20260912-120000-0002"):
        workspace.prepare_run(tmp_path, run_id)
    payload = text_of(run(tmp_path, cfg=cfg, run_id="20260912-130000-0003"))
    assert payload["ok"] is True
    surviving = workspace.existing_run_ids(tmp_path)
    assert surviving == ["20260912-130000-0003"]


def test_pruning_also_drops_the_index_entries(tmp_path: Path):
    cfg = make_config(tmp_path, keep_runs=1)
    for run_id in ("20260912-100000-0001", "20260912-120000-0002"):
        workspace.prepare_run(tmp_path, run_id)
        index.upsert_run(tmp_path, {"runId": run_id, "createdAt": "2026-09-12T10:00:00+08:00"})
    run(tmp_path, cfg=cfg, run_id="20260912-130000-0003")
    ids = [entry["runId"] for entry in index.load_index(tmp_path)["runs"]]
    assert ids == ["20260912-130000-0003"]


def test_index_write_failure_does_not_fail_the_render(tmp_path: Path, monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(pipeline.index, "upsert_run", explode)
    payload = text_of(run(tmp_path))
    assert payload["ok"] is True
    assert any("索引" in note for note in payload["warnings"])


def test_webp_preview_is_advertised_with_its_own_extension(tmp_path: Path):
    payload = text_of(run(tmp_path, preview_fn=stub_preview("webp")))
    assert payload["previewMarkdown"].endswith(".webp)")
    assert payload["assets"]["preview"].endswith(".webp")


def test_poster_only_preview_points_markdown_at_the_png(tmp_path: Path):
    payload = text_of(run(tmp_path, preview_fn=stub_preview("png")))
    assert payload["previewMarkdown"].endswith(".png)")
