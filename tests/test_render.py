"""Rendering is a subprocess contract: argv, timeout, kill, artifact discovery."""

import subprocess
from pathlib import Path

from manim_mcp.config import Config
from manim_mcp.engine import render, workspace


def make_config(**overrides) -> Config:
    base = dict(
        python=r"D:\py\python.exe",
        manim=None,
        ffmpeg=r"D:\tools\ffmpeg.exe",
        render_root=Path("."),
        max_concurrency=1,
        timeout_sec=1.0,
        gif_target_bytes=100,
        gif_max_bytes=200,
        keep_runs=1,
        log_level="INFO",
    )
    base.update(overrides)
    return Config(**base)


def make_run(tmp_path: Path):
    return workspace.prepare_run(tmp_path, "20260912-153012-a1b2")


class FakeProcess:
    """A child process whose timeout behaviour the test drives explicitly."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.pid = 4242
        self.killed = False
        self.hang = False
        self.timeouts: list[float] = []

    def communicate(self, timeout=None):
        if timeout is not None:
            self.timeouts.append(timeout)
            if self.hang and not self.killed:
                raise subprocess.TimeoutExpired(cmd="manim", timeout=timeout)
        return self.stdout, self.stderr

    def poll(self):
        return None if (self.hang and not self.killed) else self.returncode

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


def test_argv_uses_the_module_form_when_no_binary_is_pinned(tmp_path: Path):
    paths = make_run(tmp_path)
    argv = render.build_argv(make_config(), paths, "EquationScene", "draft")
    assert argv[:3] == [r"D:\py\python.exe", "-m", "manim"]
    assert argv[3] == "render"
    assert "-ql" in argv
    assert "--format=mp4" in argv
    assert str(paths.media) in argv
    assert argv[-1] == "EquationScene"


def test_argv_uses_the_pinned_binary_when_present(tmp_path: Path):
    paths = make_run(tmp_path)
    cfg = make_config(manim=r"D:\py\Scripts\manim.exe")
    argv = render.build_argv(cfg, paths, "EquationScene", "final")
    assert argv[0] == r"D:\py\Scripts\manim.exe"
    assert "-qm" in argv


def test_final_quality_uses_the_720p_flag(tmp_path: Path):
    paths = make_run(tmp_path)
    assert "-qm" in render.build_argv(make_config(), paths, "S", "final")


def test_unknown_quality_is_rejected(tmp_path: Path):
    paths = make_run(tmp_path)
    try:
        render.build_argv(make_config(), paths, "S", "cinematic")
    except ValueError as error:
        assert "cinematic" in str(error)
    else:  # pragma: no cover - the assertion above is the point
        raise AssertionError("an unknown quality must be rejected")


def test_argv_points_at_the_generated_scene_file(tmp_path: Path):
    paths = make_run(tmp_path)
    argv = render.build_argv(make_config(), paths, "S", "draft")
    assert str(paths.scene) in argv


def test_successful_render_reports_the_mp4(tmp_path: Path):
    paths = make_run(tmp_path)
    imported = paths.media / "videos" / "scene" / "480p15" / "EquationScene.mp4"
    imported.parent.mkdir(parents=True)

    captured = {}

    def popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        imported.write_bytes(b"mp4")
        return FakeProcess(returncode=0)

    result = render.render_scene(make_config(), paths, "EquationScene", "draft", popen=popen)
    assert result.ok is True
    assert result.mp4 == imported
    assert result.diagnostic is None
    assert result.seconds >= 0
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["errors"] == "replace"


def test_failing_render_returns_a_diagnostic(tmp_path: Path):
    paths = make_run(tmp_path)
    workspace.write_scene(
        paths,
        "from manim import *\n\nclass S(Scene):\n    def construct(self):\n        x = Nope()\n",
    )
    stderr = (
        "Traceback (most recent call last):\n"
        f'  File "{paths.scene}", line 5, in construct\n'
        "    x = Nope()\n"
        "NameError: name 'Nope' is not defined\n"
    )

    def popen(argv, **kwargs):
        return FakeProcess(returncode=1, stderr=stderr)

    result = render.render_scene(make_config(), paths, "S", "draft", popen=popen)
    assert result.ok is False
    assert result.mp4 is None
    assert result.diagnostic is not None
    assert result.diagnostic.type == "NameError"
    assert result.diagnostic.line == 5
    assert result.diagnostic.stage == "manim"


def test_exit_zero_without_an_artifact_is_a_failure(tmp_path: Path):
    paths = make_run(tmp_path)

    def popen(argv, **kwargs):
        return FakeProcess(returncode=0)

    result = render.render_scene(make_config(), paths, "S", "draft", popen=popen)
    assert result.ok is False
    assert result.diagnostic is not None
    assert "产物" in (result.diagnostic.message or "")


def test_nonzero_exit_without_a_traceback_still_names_the_exit_code(tmp_path: Path):
    paths = make_run(tmp_path)

    def popen(argv, **kwargs):
        return FakeProcess(returncode=3, stderr="something odd\n")

    result = render.render_scene(make_config(), paths, "S", "draft", popen=popen)
    assert result.ok is False
    assert result.diagnostic is not None
    assert "3" in (result.diagnostic.message or "")


def test_timeout_kills_the_process_tree_and_reports_timeout(tmp_path: Path):
    paths = make_run(tmp_path)
    process = FakeProcess(returncode=1, stderr="still working")
    process.hang = True
    killed: list[list[str]] = []

    def popen(argv, **kwargs):
        return process

    def run(argv, **kwargs):
        killed.append(list(argv))
        process.kill()
        return subprocess.CompletedProcess(argv, 0, "", "")

    result = render.render_scene(
        make_config(timeout_sec=2.0), paths, "S", "draft", popen=popen, run=run
    )
    assert result.ok is False
    assert result.diagnostic is not None
    assert result.diagnostic.stage == "timeout"
    assert "2" in (result.diagnostic.message or "")
    assert any(argv[0] == "taskkill" for argv in killed)


def test_missing_artifact_search_returns_none(tmp_path: Path):
    assert render.find_output_mp4(tmp_path, "Nothing") is None


def test_missing_media_dir_search_returns_none(tmp_path: Path):
    assert render.find_output_mp4(tmp_path / "absent", "S") is None


def test_artifact_search_prefers_the_newest_match(tmp_path: Path):
    import os
    import time

    older_dir = tmp_path / "videos" / "scene" / "480p15"
    older_dir.mkdir(parents=True)
    older = older_dir / "S.mp4"
    older.write_bytes(b"old")

    time.sleep(0.01)
    newer_dir = tmp_path / "videos" / "scene" / "720p30"
    newer_dir.mkdir(parents=True)
    fresh = newer_dir / "S.mp4"
    fresh.write_bytes(b"new")

    os.utime(older, (1, 1))
    assert render.find_output_mp4(tmp_path, "S") == fresh


def test_artifact_search_ignores_a_different_scene(tmp_path: Path):
    base = tmp_path / "videos" / "scene" / "480p15"
    base.mkdir(parents=True)
    (base / "Other.mp4").write_bytes(b"mp4")
    assert render.find_output_mp4(tmp_path, "S") is None
