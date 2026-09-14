"""Six ways a publish can be refused. Each one must name its reason, because the model
reads it and corrects itself — a vague failure makes it retry blindly."""

from pathlib import Path

import pytest

from media_mcp.config import load_config
from media_mcp.validate import validate


@pytest.fixture()
def cfg(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    return load_config(
        env={
            "MEDIA_MCP_ROOTS": str(root),
            "MEDIA_MCP_FS_CWD": str(root),
            "MEDIA_MCP_MAX_BYTES": "32",
        }
    ), root


def test_a_good_file_passes(cfg):
    config, root = cfg
    target = root / "ok.bin"
    target.write_bytes(b"x" * 8)
    assert validate(str(target), config) is None


def test_a_relative_path_is_refused(cfg):
    config, _ = cfg
    rejection = validate("ok.bin", config)
    assert rejection.reason == "not-absolute"
    assert rejection.hint


def test_a_missing_file_is_refused(cfg):
    config, root = cfg
    rejection = validate(str(root / "absent.bin"), config)
    assert rejection.reason == "missing"


def test_a_directory_is_refused(cfg):
    config, root = cfg
    rejection = validate(str(root), config)
    assert rejection.reason == "not-a-file"


def test_a_file_outside_every_root_is_refused(cfg, tmp_path: Path):
    config, _ = cfg
    outside = tmp_path / "elsewhere.bin"
    outside.write_bytes(b"x")
    rejection = validate(str(outside), config)
    assert rejection.reason == "outside-root"
    assert "root" in rejection.hint.lower() or "允许" in rejection.hint


def test_a_file_on_another_drive_than_the_fs_cwd_is_refused(cfg):
    """The reference carries no drive, so the Host can only supply it from fs.cwd."""
    config, root = cfg
    config_on_z = load_config(
        env={
            "MEDIA_MCP_ROOTS": "Z:/",
            "MEDIA_MCP_FS_CWD": str(root),
            "MEDIA_MCP_MAX_BYTES": "32",
        }
    )
    rejection = validate("Z:/nowhere.bin", config_on_z)
    assert rejection.reason in {"wrong-drive", "missing"}


def test_a_file_exactly_at_the_cap_passes(cfg):
    config, root = cfg
    target = root / "exact.bin"
    target.write_bytes(b"x" * 32)
    assert validate(str(target), config) is None


def test_a_file_one_byte_over_the_cap_is_refused_with_both_numbers(cfg):
    config, root = cfg
    target = root / "big.bin"
    target.write_bytes(b"x" * 33)
    rejection = validate(str(target), config)
    assert rejection.reason == "too-large"
    assert "33" in rejection.detail and "32" in rejection.detail
