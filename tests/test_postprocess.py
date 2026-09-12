"""The size ladder is the only thing standing between a render and a 20 MiB cap."""

import re
import subprocess
from pathlib import Path

from manim_mcp.engine import postprocess

FFMPEG = r"D:\tools\ffmpeg.exe"
RUNG_RE = re.compile(r"fps=(\d+).*?scale=(\d+)", re.DOTALL)


class FakeRunner:
    """Records every invocation and fabricates outputs of a prescribed size.

    Sizes are keyed `"kind:fps@width"` first, then `"kind"`, then 1024 bytes, so a
    test can pin one specific rung without describing the whole ladder.
    """

    def __init__(self, sizes=None, duration="00:00:10.00"):
        self.sizes = dict(sizes or {})
        self.duration = duration
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[0] != FFMPEG:
            raise AssertionError(f"unexpected binary {argv[0]!r}")
        out = Path(argv[-1])

        if "-y" not in argv:
            # probe_duration: ffmpeg fails on the missing output and prints a banner.
            return subprocess.CompletedProcess(
                argv, 1, "", f"  Duration: {self.duration}, start: 0"
            )

        kind = out.suffix.lstrip(".")
        rung = self.rung(argv)
        key = f"{kind}:{rung[0]}@{rung[1]}" if rung else kind
        out.write_bytes(b"x" * self.sizes.get(key, self.sizes.get(kind, 1024)))
        return subprocess.CompletedProcess(argv, 0, "", "")

    @staticmethod
    def rung(argv) -> tuple[int, int] | None:
        for item in argv:
            if isinstance(item, str) and item.startswith("fps="):
                match = RUNG_RE.search(item)
                if match:
                    return int(match.group(1)), int(match.group(2))
        return None


def encode_rungs(runner: FakeRunner, extension: str) -> list[tuple[int, int]]:
    """Ladder rungs actually used for final artifacts of one format."""
    found = []
    for call in runner.calls:
        if call[-1].endswith(extension) and "-y" in call:
            rung = FakeRunner.rung(call)
            if rung is not None:
                found.append(rung)
    return found


def build(tmp_path: Path, sizes, duration="00:00:10.00", **overrides):
    runner = FakeRunner(sizes, duration)
    preview = postprocess.build_preview(
        overrides.pop("ffmpeg", FFMPEG),
        tmp_path / "a.mp4",
        tmp_path,
        "Scene",
        target_bytes=overrides.pop("target_bytes", 1_000_000),
        max_bytes=overrides.pop("max_bytes", 2_000_000),
        run=runner,
    )
    return preview, runner


def test_probe_duration_parses_ffmpeg_output(tmp_path: Path):
    runner = FakeRunner(duration="00:00:12.40")
    assert postprocess.probe_duration(FFMPEG, tmp_path / "a.mp4", run=runner) == 12.4


def test_probe_duration_handles_hours(tmp_path: Path):
    runner = FakeRunner(duration="01:02:03.50")
    seconds = postprocess.probe_duration(FFMPEG, tmp_path / "a.mp4", run=runner)
    assert seconds == 3723.5


def test_probe_duration_returns_zero_when_unparseable(tmp_path: Path):
    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "no duration here")

    assert postprocess.probe_duration(FFMPEG, tmp_path / "a.mp4", run=runner) == 0.0


def test_short_scene_returns_the_poster_frame(tmp_path: Path):
    preview, _ = build(tmp_path, {"png": 4096}, duration="00:00:00.40")
    assert preview.kind == "png"
    assert preview.path == tmp_path / "Scene.png"
    assert preview.byte_size == 4096
    assert any("静态" in note for note in preview.warnings)


def test_first_ladder_rung_is_used_when_it_fits(tmp_path: Path):
    preview, runner = build(tmp_path, {"gif": 500_000})
    assert preview.kind == "gif"
    assert preview.byte_size == 500_000
    assert preview.warnings == ()
    assert encode_rungs(runner, ".gif") == [(15, 800)]


def test_overshoot_of_the_target_is_reported_but_accepted(tmp_path: Path):
    preview, _ = build(tmp_path, {"gif": 1_500_000})
    assert preview.kind == "gif"
    assert any("目标体积" in note for note in preview.warnings)


def test_ladder_degrades_fps_and_width_before_giving_up(tmp_path: Path):
    preview, runner = build(
        tmp_path,
        {"gif:15@800": 2_100_000, "gif:12@800": 2_100_000, "gif:12@640": 900_000},
    )
    assert preview.kind == "gif"
    assert preview.byte_size == 900_000
    assert encode_rungs(runner, ".gif") == [(15, 800), (12, 800), (12, 640)]


def test_falls_back_to_webp_when_every_gif_rung_overshoots(tmp_path: Path):
    preview, runner = build(tmp_path, {"gif": 3_000_000, "webp": 400_000})
    assert preview.kind == "webp"
    assert preview.byte_size == 400_000
    assert preview.path is not None and preview.path.suffix == ".webp"
    assert len(encode_rungs(runner, ".gif")) == len(postprocess.LADDER)
    assert encode_rungs(runner, ".webp") == [(15, 800)]


def test_falls_back_to_the_poster_when_both_formats_overshoot(tmp_path: Path):
    preview, _ = build(tmp_path, {"gif": 3_000_000, "webp": 3_000_000, "png": 50_000})
    assert preview.kind == "png"
    assert preview.byte_size == 50_000
    assert any("硬上限" in note for note in preview.warnings)


def test_overshooting_artifacts_are_deleted(tmp_path: Path):
    build(tmp_path, {"gif": 3_000_000, "webp": 3_000_000, "png": 50_000})
    assert not (tmp_path / "Scene.gif").exists()
    assert not (tmp_path / "Scene.webp").exists()


def test_palette_file_is_cleaned_up(tmp_path: Path):
    build(tmp_path, {"gif": 500_000})
    assert not list(tmp_path.glob("*.palette.png"))


def test_poster_is_taken_from_the_last_frame(tmp_path: Path):
    _, runner = build(tmp_path, {"gif": 500_000})
    poster_call = [call for call in runner.calls if call[-1].endswith("Scene.png")][0]
    assert "-sseof" in poster_call


def test_poster_is_produced_even_when_a_gif_wins(tmp_path: Path):
    build(tmp_path, {"gif": 500_000})
    assert (tmp_path / "Scene.png").exists()


def test_missing_ffmpeg_yields_no_preview(tmp_path: Path):
    preview = postprocess.build_preview(
        None, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000,
    )
    assert preview.path is None
    assert preview.kind is None
    assert preview.byte_size == 0
    assert any("ffmpeg" in note for note in preview.warnings)


def test_mime_lookup_covers_every_preview_kind():
    assert postprocess.MIME_BY_KIND == {
        "gif": "image/gif",
        "webp": "image/webp",
        "png": "image/png",
    }


def test_ladder_is_ordered_from_finest_to_coarsest():
    ladder = postprocess.LADDER
    assert ladder[0] == (15, 800)
    assert ladder[-1] == (10, 480)
    assert [fps for fps, _ in ladder] == sorted((fps for fps, _ in ladder), reverse=True)
