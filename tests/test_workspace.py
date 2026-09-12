"""Run directories: safe names, stable layout, honest retention."""

from datetime import datetime
from pathlib import Path

import pytest

from manim_mcp.engine import workspace


def test_run_id_is_ascii_and_filesystem_safe():
    run_id = workspace.new_run_id(datetime(2026, 9, 12, 15, 30, 12), token="a1b2")
    assert run_id == "20260912-153012-a1b2"
    assert workspace.is_valid_run_id(run_id)


def test_generated_run_ids_are_valid_and_unique():
    """A collision would silently overwrite an earlier run's directory."""
    ids = {workspace.new_run_id() for _ in range(200)}
    assert len(ids) == 200
    assert all(workspace.is_valid_run_id(value) for value in ids)


def test_generated_suffix_has_enough_entropy_for_same_second_renders():
    from datetime import datetime as _datetime

    frozen = _datetime(2026, 9, 12, 15, 30, 12)
    ids = {workspace.new_run_id(frozen) for _ in range(500)}
    assert len(ids) == 500


def test_underscore_and_space_are_rejected():
    assert not workspace.is_valid_run_id("20260912-153012_a1b2")
    assert not workspace.is_valid_run_id("20260912 153012-a1b2")


def test_missing_suffix_is_rejected():
    assert not workspace.is_valid_run_id("20260912-153012")


def test_uppercase_hex_is_rejected_so_names_stay_predictable():
    assert not workspace.is_valid_run_id("20260912-153012-A1B2")


def test_empty_run_id_is_rejected():
    assert not workspace.is_valid_run_id("")
    assert not workspace.is_valid_run_id(None)


def test_prepare_run_creates_the_expected_tree(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    assert paths.root == tmp_path / "20260912-153012-a1b2"
    assert paths.media.is_dir()
    assert paths.out.is_dir()
    assert paths.scene == paths.root / "scene.py"
    assert paths.meta == paths.root / "run.json"


def test_run_paths_describes_without_creating(tmp_path: Path):
    paths = workspace.run_paths(tmp_path, "20260912-153012-a1b2")
    assert paths.root == tmp_path / "20260912-153012-a1b2"
    assert not paths.root.exists()


def test_prepare_run_is_idempotent(tmp_path: Path):
    first = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    workspace.write_scene(first, "print('hi')\n")
    second = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    assert workspace.read_scene(second) == "print('hi')\n"


def test_prepare_run_rejects_an_unsafe_id(tmp_path: Path):
    with pytest.raises(workspace.WorkspaceError):
        workspace.prepare_run(tmp_path, "../escape")


def test_scene_round_trips_unicode(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    workspace.write_scene(paths, "# 中文注释\nx = 1\n")
    assert "中文注释" in workspace.read_scene(paths)


def test_write_scene_returns_the_path(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    assert workspace.write_scene(paths, "x = 1\n") == paths.scene


def test_meta_round_trips_and_tolerates_a_missing_file(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    assert workspace.read_meta(paths) is None
    workspace.write_meta(paths, {"runId": paths.run_id, "status": "ok"})
    assert workspace.read_meta(paths) == {"runId": paths.run_id, "status": "ok"}


def test_corrupt_meta_reads_as_none(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    paths.meta.write_text("{ not json", encoding="utf-8")
    assert workspace.read_meta(paths) is None


def test_non_object_meta_reads_as_none(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    paths.meta.write_text("[1, 2, 3]", encoding="utf-8")
    assert workspace.read_meta(paths) is None


def test_meta_preserves_unicode(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    workspace.write_meta(paths, {"title": "欧拉恒等式"})
    assert workspace.read_meta(paths)["title"] == "欧拉恒等式"


def test_read_meta_at_accepts_a_bare_directory(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    workspace.write_meta(paths, {"runId": paths.run_id})
    assert workspace.read_meta_at(paths.root) == {"runId": paths.run_id}
    assert workspace.read_meta_at(tmp_path / "absent") is None


def test_existing_run_ids_are_newest_first(tmp_path: Path):
    for run_id in ("20260912-100000-0001", "20260912-120000-0002", "20260912-110000-0003"):
        workspace.prepare_run(tmp_path, run_id)
    (tmp_path / "not-a-run").mkdir()
    assert workspace.existing_run_ids(tmp_path) == [
        "20260912-120000-0002",
        "20260912-110000-0003",
        "20260912-100000-0001",
    ]


def test_existing_run_ids_ignores_files(tmp_path: Path):
    (tmp_path / "20260912-100000-0001").write_text("not a directory", encoding="utf-8")
    assert workspace.existing_run_ids(tmp_path) == []


def test_missing_root_lists_nothing(tmp_path: Path):
    assert workspace.existing_run_ids(tmp_path / "absent") == []


def test_prune_keeps_the_newest_and_reports_deletions(tmp_path: Path):
    ids = ["20260912-100000-0001", "20260912-110000-0002", "20260912-120000-0003"]
    for run_id in ids:
        workspace.prepare_run(tmp_path, run_id)
    removed = workspace.prune_runs(tmp_path, keep=2)
    assert removed == ["20260912-100000-0001"]
    assert workspace.existing_run_ids(tmp_path) == ids[::-1][:2]


def test_prune_with_zero_keeps_everything(tmp_path: Path):
    workspace.prepare_run(tmp_path, "20260912-100000-0001")
    assert workspace.prune_runs(tmp_path, keep=0) == []
    assert workspace.existing_run_ids(tmp_path) == ["20260912-100000-0001"]


def test_prune_is_a_noop_when_under_the_limit(tmp_path: Path):
    workspace.prepare_run(tmp_path, "20260912-100000-0001")
    assert workspace.prune_runs(tmp_path, keep=50) == []


def test_prune_on_a_missing_root_is_a_noop(tmp_path: Path):
    assert workspace.prune_runs(tmp_path / "absent", keep=1) == []


def test_prune_removes_the_whole_tree(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-100000-0001")
    workspace.write_scene(paths, "x = 1\n")
    (paths.out / "artifact.gif").write_bytes(b"gif")
    workspace.prune_runs(tmp_path, keep=0 + 1)
    workspace.prepare_run(tmp_path, "20260912-120000-0002")
    workspace.prune_runs(tmp_path, keep=1)
    assert not paths.root.exists()
