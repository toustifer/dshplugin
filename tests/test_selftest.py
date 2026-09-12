"""The self-test is the installer's proof; it must fail loudly, not politely."""

from pathlib import Path

from manim_mcp.config import Config
from manim_mcp.engine import workspace
from manim_mcp.tools import selftest


def make_config(tmp_path: Path, **overrides) -> Config:
    base = dict(
        python=r"D:\py\python.exe", manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe", render_root=tmp_path,
        max_concurrency=1, timeout_sec=30.0, gif_target_bytes=1000,
        gif_max_bytes=2000, keep_runs=50, log_level="INFO",
    )
    base.update(overrides)
    return Config(**base)


def test_missing_ffmpeg_exits_two_and_creates_no_run(tmp_path: Path):
    assert selftest.run(make_config(tmp_path, ffmpeg=None)) == 2
    assert workspace.existing_run_ids(tmp_path) == []


def test_successful_run_exits_zero_and_reports_artifacts(tmp_path: Path, capsys):
    from manim_mcp.engine.postprocess import Preview
    from manim_mcp.engine.render import RenderResult

    def fake_render(cfg, paths, scene_class, quality):
        artifact = paths.out / f"{scene_class}.mp4"
        artifact.write_bytes(b"mp4")
        return RenderResult(ok=True, mp4=artifact, seconds=4.2)

    def fake_preview(ffmpeg, mp4, out_dir, basename, **kwargs):
        path = out_dir / f"{basename}.gif"
        path.write_bytes(b"g" * 500)
        return Preview(path=path, kind="gif", byte_size=500)

    code = lambda: "from manim import *\n"  # noqa: E731
    assert selftest.run(
        make_config(tmp_path),
        build_code=code,
        render_fn=fake_render,
        preview_fn=fake_preview,
    ) == 0

    printed = capsys.readouterr().out
    assert "manim" in printed
    assert ".gif" in printed or ".mp4" in printed
    assert "self-test PASSED" in printed


def test_failed_render_exits_one_with_the_hint(tmp_path: Path, capsys):
    from manim_mcp.engine.diagnostics import Diagnostic
    from manim_mcp.engine.render import RenderResult

    def fake_render(cfg, paths, scene_class, quality):
        return RenderResult(
            ok=False, mp4=None, seconds=1.0,
            diagnostic=Diagnostic(stage="manim", type="NameError", message="boom", hint="加 import"),
        )

    assert selftest.run(
        make_config(tmp_path),
        build_code=lambda: "from manim import *\n",
        render_fn=fake_render,
    ) == 1
    captured = capsys.readouterr()
    assert "boom" in captured.out + captured.err
    assert "加 import" in captured.out + captured.err


def test_selftest_scene_uses_chinese_a_formula_and_a_shape():
    code = selftest.sample_scene("SimHei")
    assert "cn(" in code
    assert "MathTex" in code
    assert "Circle" in code
    assert "SimHei" in code


def test_selftest_scene_compiles_without_a_cjk_font():
    compile(selftest.sample_scene(None), "<selftest>", "exec")
