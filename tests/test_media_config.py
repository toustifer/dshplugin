"""Config is the only place the environment is read; everything else takes a Config."""

from pathlib import Path

import pytest

from media_mcp.config import Config, load_config


def test_defaults_pin_the_render_root_to_the_repo():
    cfg = load_config(env={})
    # parents[2] of media-mcp/media_mcp/config.py is the repo root.
    assert cfg.render_root.name == "renders"
    assert cfg.render_root.parent.name == "dshplugin"


def test_roots_default_to_the_single_repo_root():
    cfg = load_config(env={})
    assert len(cfg.roots) == 1
    assert cfg.roots[0] == cfg.render_root.parent


def test_fs_cwd_defaults_to_the_same_root_the_installer_pins():
    """A second source of truth here is how the reference silently 404s."""
    cfg = load_config(env={})
    assert cfg.fs_cwd == cfg.render_root.parent


def test_env_overrides_are_parsed():
    cfg = load_config(
        env={
            "MEDIA_MCP_ROOTS": r"D:\a;D:\b",
            "MEDIA_MCP_MAX_BYTES": "1024",
            "MEDIA_MCP_PDF_PAGES": "5",
            "MEDIA_MCP_PDF_DPI": "72",
        }
    )
    assert [p.name for p in cfg.roots] == ["a", "b"]
    assert cfg.max_bytes == 1024
    assert cfg.pdf_pages == 5
    assert cfg.pdf_dpi == 72


def test_a_bad_numeric_override_fails_loudly():
    """Silently falling back to the default would publish files the cap was meant to stop."""
    with pytest.raises(ValueError):
        load_config(env={"MEDIA_MCP_MAX_BYTES": "twenty"})


def test_doctor_reports_every_path_it_depends_on():
    report = load_config(env={}).doctor()
    assert set(report) >= {
        "python",
        "pdftoppm",
        "pdfinfo",
        "renderRoot",
        "fsCwd",
        "roots",
        "maxBytes",
        "pdftoppmFound",
        "pdfinfoFound",
    }
    assert isinstance(report["roots"], list)
