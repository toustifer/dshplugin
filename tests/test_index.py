"""The gallery reads index.json, so it must survive every way a file can be wrong."""

import json
import os
from pathlib import Path

from manim_mcp.engine import index, workspace


def _entry(run_id: str, created: str, status: str = "ok") -> dict:
    return {
        "runId": run_id,
        "tool": "equation",
        "status": status,
        "createdAt": created,
        "assets": {"preview": f"D:/r/{run_id}/out/s.gif", "previewKind": "gif"},
        "previewUrlPath": f"/D:/r/{run_id}/out/s.gif",
    }


def test_missing_index_loads_as_empty(tmp_path: Path):
    data = index.load_index(tmp_path)
    assert data["version"] == index.INDEX_VERSION
    assert data["runs"] == []
    assert data["updatedAt"] is None


def test_corrupt_index_loads_as_empty(tmp_path: Path):
    index.index_path(tmp_path).write_text("<<<not json>>>", encoding="utf-8")
    assert index.load_index(tmp_path)["runs"] == []


def test_wrong_shape_loads_as_empty(tmp_path: Path):
    index.index_path(tmp_path).write_text(json.dumps(["a", "list"]), encoding="utf-8")
    assert index.load_index(tmp_path)["runs"] == []


def test_runs_not_a_list_loads_as_empty(tmp_path: Path):
    index.index_path(tmp_path).write_text(json.dumps({"runs": {}}), encoding="utf-8")
    assert index.load_index(tmp_path)["runs"] == []


def test_upsert_appends_and_sorts_newest_first(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    index.upsert_run(tmp_path, _entry("2", "2026-09-12T12:00:00+08:00"))
    index.upsert_run(tmp_path, _entry("3", "2026-09-12T11:00:00+08:00"))
    ids = [run["runId"] for run in index.load_index(tmp_path)["runs"]]
    assert ids == ["2", "3", "1"]


def test_upsert_replaces_the_same_run_id(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00", status="failed"))
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00", status="ok"))
    runs = index.load_index(tmp_path)["runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "ok"


def test_save_stamps_version_and_timestamp(tmp_path: Path):
    data = index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    assert data["version"] == index.INDEX_VERSION
    assert isinstance(data["updatedAt"], str)
    assert data["updatedAt"]


def test_save_index_returns_exactly_what_is_on_disk(tmp_path: Path):
    returned = index.save_index(tmp_path, {"runs": [_entry("1", "2026-09-12T10:00:00+08:00")]})
    assert returned == index.load_index(tmp_path)


def test_save_leaves_no_temp_file_behind(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_save_replaces_rather_than_truncating_in_place(tmp_path: Path):
    """A reader must never observe a partially written index."""
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    seen: list[str] = []
    real_replace = os.replace

    def spy(src, dst):
        # The destination still holds the previous generation at swap time.
        seen.append(Path(dst).read_text(encoding="utf-8"))
        return real_replace(src, dst)

    os.replace = spy
    try:
        index.upsert_run(tmp_path, _entry("2", "2026-09-12T12:00:00+08:00"))
    finally:
        os.replace = real_replace

    assert len(seen) == 1
    assert json.loads(seen[0])["runs"][0]["runId"] == "1"


def test_save_creates_the_root_directory(tmp_path: Path):
    nested = tmp_path / "deep" / "renders"
    index.upsert_run(nested, _entry("1", "2026-09-12T10:00:00+08:00"))
    assert index.index_path(nested).exists()


def test_remove_drops_only_the_named_run(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    index.upsert_run(tmp_path, _entry("2", "2026-09-12T12:00:00+08:00"))
    data = index.remove_run(tmp_path, "1")
    assert [run["runId"] for run in data["runs"]] == ["2"]


def test_remove_of_an_unknown_run_is_a_noop(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    data = index.remove_run(tmp_path, "nope")
    assert [run["runId"] for run in data["runs"]] == ["1"]


def test_remove_creates_an_index_when_none_existed(tmp_path: Path):
    data = index.remove_run(tmp_path, "nope")
    assert data["runs"] == []
    assert index.index_path(tmp_path).exists()


def test_rebuild_sorts_and_drops_entries_without_metadata(tmp_path: Path):
    for run_id, created in (
        ("20260912-100000-0001", "2026-09-12T10:00:00+08:00"),
        ("20260912-120000-0002", "2026-09-12T12:00:00+08:00"),
    ):
        paths = workspace.prepare_run(tmp_path, run_id)
        workspace.write_meta(paths, _entry(run_id, created))
    workspace.prepare_run(tmp_path, "20260912-110000-0003")  # no run.json
    (tmp_path / "not-a-run").mkdir()

    data = index.rebuild_index(tmp_path)
    assert [run["runId"] for run in data["runs"]] == [
        "20260912-120000-0002",
        "20260912-100000-0001",
    ]


def test_rebuild_fills_in_a_missing_run_id_from_the_directory_name(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-100000-0001")
    workspace.write_meta(paths, {"createdAt": "2026-09-12T10:00:00+08:00"})
    runs = index.rebuild_index(tmp_path)["runs"]
    assert runs[0]["runId"] == "20260912-100000-0001"


def test_rebuild_drops_entries_whose_directory_vanished(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("20260912-100000-0001", "2026-09-12T10:00:00+08:00"))
    assert index.rebuild_index(tmp_path)["runs"] == []


def test_rebuild_on_a_missing_root_is_empty(tmp_path: Path):
    assert index.rebuild_index(tmp_path / "absent")["runs"] == []


def test_rebuild_preserves_unicode_titles(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-100000-0001")
    workspace.write_meta(
        paths, {"runId": paths.run_id, "title": "欧拉恒等式", "createdAt": "2026-09-12T10:00:00+08:00"}
    )
    assert index.rebuild_index(tmp_path)["runs"][0]["title"] == "欧拉恒等式"
