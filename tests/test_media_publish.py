"""The tool body wires the parts together. Its job is the ORDER: validate, then sniff,
then reference, then (for PDF only) rasterise."""

from pathlib import Path

import pytest

from media_mcp.config import load_config
from media_mcp.tools.publish import publish


@pytest.fixture()
def cfg(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    return load_config(
        env={
            "MEDIA_MCP_ROOTS": str(root),
            "MEDIA_MCP_FS_CWD": str(root),
            "MEDIA_MCP_MAX_BYTES": "1000000",
        }
    ), root


def test_a_video_publishes_with_a_video_descriptor(cfg):
    config, root = cfg
    target = root / "clip.mp4"
    target.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32)
    payload = publish(str(target), None, config)
    assert payload["ok"] is True
    assert payload["media"]["kind"] == "video"
    assert payload["media"]["mime"] == "video/mp4"
    assert payload["media"]["reference"].endswith("/clip.mp4")
    assert payload["extras"] == []


def test_a_rejection_short_circuits_before_any_reference_is_minted(cfg):
    config, root = cfg
    payload = publish(str(root / "absent.mp4"), None, config)
    assert payload["ok"] is False
    assert payload["reason"] == "missing"
    assert "media" not in payload


def test_the_title_reaches_the_descriptor(cfg):
    config, root = cfg
    target = root / "a.png"
    target.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 16)
    payload = publish(str(target), "示意图", config)
    assert payload["media"]["title"] == "示意图"


def test_a_pdf_carries_its_rasterised_pages_as_extras(cfg, monkeypatch):
    config, root = cfg
    target = root / "report.pdf"
    target.write_bytes(b"%PDF-1.7\n" + b"\x00" * 32)
    page = root / "page-1.png"
    page.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 16)
    monkeypatch.setattr(
        "media_mcp.tools.publish.rasterize", lambda pdf, cfg_: ([page], 3, [])
    )
    payload = publish(str(target), None, config)
    assert payload["ok"] is True
    assert payload["media"]["kind"] == "pdf"
    assert [item["kind"] for item in payload["extras"]] == ["image"]
    assert payload["extras"][0]["reference"].endswith("/page-1.png")


def test_a_failed_rasterisation_still_publishes_the_pdf(cfg, monkeypatch):
    config, root = cfg
    target = root / "report.pdf"
    target.write_bytes(b"%PDF-1.7\n" + b"\x00" * 32)
    monkeypatch.setattr(
        "media_mcp.tools.publish.rasterize", lambda pdf, cfg_: ([], None, ["坏了"])
    )
    payload = publish(str(target), None, config)
    assert payload["ok"] is True
    assert payload["extras"] == []
    assert "坏了" in payload["warnings"]
