"""Configuration parsing must be total: bad input raises, absent input defaults."""

import sys
from pathlib import Path

import pytest

from manim_mcp import config as config_mod
from manim_mcp.config import ConfigError, load_config


def test_defaults_when_env_is_empty():
    cfg = load_config(env={})
    assert cfg.python == sys.executable
    assert cfg.render_root == config_mod.DEFAULT_RENDER_ROOT
    assert cfg.max_concurrency == 1
    assert cfg.timeout_sec == 180.0
    assert cfg.gif_target_bytes == 8 * 1024 * 1024
    assert cfg.gif_max_bytes == 18 * 1024 * 1024
    assert cfg.keep_runs == 50
    assert cfg.log_level == "INFO"


def test_env_overrides_are_read():
    cfg = load_config(env={
        "MANIM_MCP_PYTHON": r"D:\py\python.exe",
        "MANIM_MCP_MANIM": r"D:\py\Scripts\manim.exe",
        "MANIM_MCP_FFMPEG": r"D:\tools\ffmpeg.exe",
        "MANIM_MCP_RENDER_ROOT": r"D:\out",
        "MANIM_MCP_MAX_CONCURRENCY": "3",
        "MANIM_MCP_TIMEOUT_SEC": "45.5",
        "MANIM_MCP_KEEP_RUNS": "0",
        "MANIM_MCP_LOG_LEVEL": "DEBUG",
    })
    assert cfg.python == r"D:\py\python.exe"
    assert cfg.manim == r"D:\py\Scripts\manim.exe"
    assert cfg.ffmpeg == r"D:\tools\ffmpeg.exe"
    assert cfg.render_root == Path(r"D:\out")
    assert cfg.max_concurrency == 3
    assert cfg.timeout_sec == 45.5
    assert cfg.keep_runs == 0
    assert cfg.log_level == "DEBUG"


def test_non_integer_number_is_rejected():
    with pytest.raises(ConfigError) as caught:
        load_config(env={"MANIM_MCP_MAX_CONCURRENCY": "many"})
    assert "MANIM_MCP_MAX_CONCURRENCY" in str(caught.value)


def test_negative_concurrency_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_MAX_CONCURRENCY": "-1"})


def test_zero_concurrency_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_MAX_CONCURRENCY": "0"})


def test_zero_keep_runs_is_allowed():
    assert load_config(env={"MANIM_MCP_KEEP_RUNS": "0"}).keep_runs == 0


def test_target_must_not_exceed_hard_cap():
    with pytest.raises(ConfigError) as caught:
        load_config(env={
            "MANIM_MCP_GIF_TARGET_BYTES": "20000000",
            "MANIM_MCP_GIF_MAX_BYTES": "10000000",
        })
    assert "GIF_TARGET_BYTES" in str(caught.value)


def test_manim_argv_prefers_the_explicit_binary():
    cfg = load_config(env={"MANIM_MCP_MANIM": r"D:\py\Scripts\manim.exe"})
    assert config_mod.manim_argv(cfg, "render") == [r"D:\py\Scripts\manim.exe", "render"]


def test_manim_argv_falls_back_to_module_invocation():
    cfg = config_mod.Config(
        python=r"D:\py\python.exe", manim=None, ffmpeg=None,
        render_root=Path("."), max_concurrency=1, timeout_sec=1.0,
        gif_target_bytes=1, gif_max_bytes=2, keep_runs=0, log_level="info",
    )
    assert config_mod.manim_argv(cfg, "render") == [
        r"D:\py\python.exe", "-m", "manim", "render",
    ]


def test_log_level_is_normalised_to_upper_case():
    assert load_config(env={"MANIM_MCP_LOG_LEVEL": "debug"}).log_level == "DEBUG"


def test_invalid_log_level_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_LOG_LEVEL": "chatty"})


def test_zero_timeout_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_TIMEOUT_SEC": "0"})


def test_non_numeric_timeout_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_TIMEOUT_SEC": "soon"})


def test_resolve_manim_returns_none_only_when_nothing_is_available(monkeypatch):
    monkeypatch.setattr(config_mod.shutil, "which", lambda name: None)
    assert config_mod.resolve_manim({}) is None
    assert config_mod.resolve_ffmpeg({}) is None


def test_blank_env_values_fall_back_to_defaults():
    cfg = load_config(env={"MANIM_MCP_PYTHON": "   ", "MANIM_MCP_KEEP_RUNS": ""})
    assert cfg.python == sys.executable
    assert cfg.keep_runs == 50


def test_python_argv_prefixes_the_interpreter():
    cfg = load_config(env={"MANIM_MCP_PYTHON": r"D:\py\python.exe"})
    assert config_mod.python_argv(cfg, "-V") == [r"D:\py\python.exe", "-V"]


def test_doctor_reports_every_dependency_row():
    cfg = load_config(env={})
    names = [row[0] for row in config_mod.doctor(cfg)]
    assert names == ["python", "manim", "ffmpeg", "latex", "render_root"]
    assert all(isinstance(row[1], bool) for row in config_mod.doctor(cfg))
