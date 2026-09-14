from pathlib import Path

from media_mcp.config import load_config
from media_mcp.selftest import run


def test_selftest_publishes_a_real_png(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    cfg = load_config(
        env={
            "MEDIA_MCP_ROOTS": str(root),
            "MEDIA_MCP_FS_CWD": str(root),
        }
    )
    code = run(cfg)
    assert code == 0


def test_selftest_fails_when_it_cannot_publish(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    cfg = load_config(
        env={"MEDIA_MCP_ROOTS": str(root), "MEDIA_MCP_FS_CWD": str(root)}
    )
    monkeypatch.setattr("media_mcp.selftest.publish", lambda *a, **k: {"ok": False})
    assert run(cfg) == 1
