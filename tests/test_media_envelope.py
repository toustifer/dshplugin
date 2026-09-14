"""One shape for both outcomes. The renderer parses this, so the keys are a contract."""

from pathlib import Path

from media_mcp.envelope import descriptor, failure, success
from media_mcp.validate import Rejection


def test_descriptor_carries_everything_the_renderer_needs(tmp_path: Path):
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"x" * 10)
    item = descriptor(
        target,
        reference="/a/clip.mp4",
        kind="video",
        mime="video/mp4",
        title="演示",
        warnings=[],
    )
    assert item["kind"] == "video"
    assert item["mime"] == "video/mp4"
    assert item["name"] == "clip.mp4"
    assert item["bytes"] == 10
    assert item["reference"] == "/a/clip.mp4"
    assert item["path"].endswith("clip.mp4")
    assert item["title"] == "演示"
    assert item["warnings"] == []


def test_descriptor_omits_an_empty_title(tmp_path: Path):
    target = tmp_path / "a.png"
    target.write_bytes(b"x")
    item = descriptor(
        target, reference="/a/a.png", kind="image", mime="image/png", title=None, warnings=[]
    )
    assert "title" not in item


def test_success_lists_the_primary_media_first():
    primary = {"kind": "pdf", "name": "r.pdf"}
    pages = [{"kind": "image", "name": "page-01.png"}]
    payload = success(primary, extras=pages, warnings=["w"])
    assert payload["ok"] is True
    assert payload["media"] == primary
    assert payload["extras"] == pages
    assert payload["warnings"] == ["w"]


def test_failure_names_the_reason_and_hints(tmp_path: Path):
    payload = failure(Rejection("too-large", "33 > 32", "压缩后再发"))
    assert payload["ok"] is False
    assert payload["reason"] == "too-large"
    assert payload["detail"] == "33 > 32"
    assert payload["hint"] == "压缩后再发"
    assert "media" not in payload
