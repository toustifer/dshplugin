"""`runs` exists so "改一下刚才那个动画" does not need the whole scene in context."""

from pathlib import Path

from manim_mcp.engine import index, workspace
from manim_mcp.tools import runs


def seed(tmp_path: Path, run_id: str, created: str, code: str = "from manim import *\n") -> None:
    paths = workspace.prepare_run(tmp_path, run_id)
    workspace.write_scene(paths, code)
    workspace.write_meta(
        paths,
        {
            "runId": run_id,
            "tool": "equation",
            "title": "欧拉恒等式",
            "status": "ok",
            "createdAt": created,
            "assets": {
                "preview": f"/tmp/{run_id}/out/S.gif",
                "previewKind": "gif",
                "mp4": f"/tmp/{run_id}/out/S.mp4",
            },
            "previewUrlPath": f"/tmp/{run_id}/out/S.gif",
        },
    )
    index.upsert_run(tmp_path, workspace.read_meta(paths))


def test_list_returns_newest_first_with_summaries(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    seed(tmp_path, "20260912-120000-0002", "2026-09-12T12:00:00+08:00")

    payload = runs.list_runs(tmp_path)
    assert payload["ok"] is True
    assert [row["runId"] for row in payload["runs"]] == [
        "20260912-120000-0002",
        "20260912-100000-0001",
    ]
    assert payload["runs"][0]["title"] == "欧拉恒等式"


def test_list_omits_the_scene_source(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00", "# secret\n")
    assert "source" not in runs.list_runs(tmp_path)["runs"][0]


def test_list_rebuilds_when_the_index_is_missing(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    index.index_path(tmp_path).unlink()
    payload = runs.list_runs(tmp_path)
    assert [row["runId"] for row in payload["runs"]] == ["20260912-100000-0001"]


def test_list_honours_the_limit(tmp_path: Path):
    for offset in range(5):
        seed(
            tmp_path,
            f"20260912-1{offset}0000-000{offset}",
            f"2026-09-12T1{offset}:00:00+08:00",
        )
    assert len(runs.list_runs(tmp_path, limit=2)["runs"]) == 2


def test_list_rejects_a_non_positive_limit(tmp_path: Path):
    payload = runs.list_runs(tmp_path, limit=0)
    assert payload["ok"] is False
    assert any("limit" in issue for issue in payload["issues"])


def test_list_on_an_empty_root_succeeds_with_no_runs(tmp_path: Path):
    payload = runs.list_runs(tmp_path)
    assert payload["ok"] is True
    assert payload["runs"] == []


def test_get_returns_the_full_source(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00", "# hello\nx=1\n")
    payload = runs.get_run(tmp_path, "20260912-100000-0001")
    assert payload["ok"] is True
    assert payload["source"] == "# hello\nx=1\n"
    assert payload["runId"] == "20260912-100000-0001"


def test_get_rejects_an_unknown_run(tmp_path: Path):
    payload = runs.get_run(tmp_path, "20260912-100000-0001")
    assert payload["ok"] is False
    assert any("不存在" in issue for issue in payload["issues"])


def test_get_rejects_a_malformed_run_id(tmp_path: Path):
    payload = runs.get_run(tmp_path, "../escape")
    assert payload["ok"] is False


def test_get_reports_a_missing_scene_file(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    (tmp_path / "20260912-100000-0001" / "scene.py").unlink()
    payload = runs.get_run(tmp_path, "20260912-100000-0001")
    assert payload["ok"] is False


def test_dispatch_routes_both_actions(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    assert runs.dispatch(tmp_path, "list")["ok"] is True
    assert runs.dispatch(tmp_path, "get", "20260912-100000-0001")["ok"] is True


def test_dispatch_rejects_an_unknown_action(tmp_path: Path):
    payload = runs.dispatch(tmp_path, "delete")
    assert payload["ok"] is False
    assert any("action" in issue for issue in payload["issues"])
