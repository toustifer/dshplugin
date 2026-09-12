"""MP4 → animated GIF / WebP / PNG preview, with an honest size ladder.

DSH's `/api/file` serves at most 20 MiB per file, and an oversized preview is a
silent failure for the user. So the encoder walks a fixed ladder, and when GIF
cannot get under the cap at any rung it moves to WebP before finally settling on
a single poster frame.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# (fps, width) tried in order. Later rungs trade smoothness for resolution.
LADDER: tuple[tuple[int, int], ...] = ((15, 800), (12, 800), (12, 640), (10, 480))
ANIMATED_KINDS = ("gif", "webp")
STATIC_SECONDS = 1.0
PROBE_TIMEOUT_SEC = 60
ENCODE_TIMEOUT_SEC = 180

DURATION_RE = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")

MIME_BY_KIND = {"gif": "image/gif", "webp": "image/webp", "png": "image/png"}


@dataclass(frozen=True)
class Preview:
    """The preview artifact, or an explicit absence with a reason."""

    path: Path | None
    kind: str | None
    byte_size: int
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _run(argv: list[str], *, timeout: int, run=None) -> subprocess.CompletedProcess:
    runner = run or subprocess.run
    return runner(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def probe_duration(ffmpeg: str, mp4: Path, *, run=None) -> float:
    """Seconds of video, or 0.0 when ffmpeg cannot say.

    ffmpeg has no "print metadata" mode, so we let it fail on the missing output
    and read the duration out of its banner.
    """
    result = _run(
        [ffmpeg, "-hide_banner", "-i", str(mp4)], timeout=PROBE_TIMEOUT_SEC, run=run
    )
    match = DURATION_RE.search(result.stderr or "")
    if match is None:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_poster(ffmpeg: str, mp4: Path, out_png: Path, *, run=None) -> Path:
    """The *last* frame: an animation's final state is its conclusion."""
    _run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-sseof", "-0.1", "-i", str(mp4),
            "-frames:v", "1", str(out_png),
        ],
        timeout=ENCODE_TIMEOUT_SEC,
        run=run,
    )
    return out_png


def encode_animated(
    ffmpeg: str, mp4: Path, out: Path, fps: int, width: int, kind: str, *, run=None
) -> Path:
    """Encode one rung of the ladder."""
    if kind == "gif":
        palette = out.with_suffix(".palette.png")
        _run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4),
                "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,palettegen=stats_mode=diff",
                str(palette),
            ],
            timeout=ENCODE_TIMEOUT_SEC,
            run=run,
        )
        _run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(mp4), "-i", str(palette),
                "-lavfi",
                f"fps={fps},scale={width}:-1:flags=lanczos[x];"
                "[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                str(out),
            ],
            timeout=ENCODE_TIMEOUT_SEC,
            run=run,
        )
        palette.unlink(missing_ok=True)
        return out

    _run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4),
            "-vf", f"fps={fps},scale={width}:-1:flags=lanczos",
            "-c:v", "libwebp", "-lossless", "0", "-q:v", "70", "-loop", "0",
            str(out),
        ],
        timeout=ENCODE_TIMEOUT_SEC,
        run=run,
    )
    return out


def _size_of(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def build_preview(
    ffmpeg: str | None,
    mp4: Path,
    out_dir: Path,
    basename: str,
    *,
    target_bytes: int,
    max_bytes: int,
    run=None,
) -> Preview:
    """Produce the smallest acceptable preview for `mp4`."""
    if not ffmpeg:
        return Preview(
            path=None,
            kind=None,
            byte_size=0,
            warnings=("ffmpeg 不可用，未生成预览图",),
        )

    poster = out_dir / f"{basename}.png"
    duration = probe_duration(ffmpeg, mp4, run=run)
    extract_poster(ffmpeg, mp4, poster, run=run)

    if duration < STATIC_SECONDS:
        size = _size_of(poster)
        return Preview(
            path=poster if poster.exists() else None,
            kind="png" if poster.exists() else None,
            byte_size=size,
            warnings=(f"静态场景（{duration:.2f}s）：只输出海报帧",),
        )

    for kind in ANIMATED_KINDS:
        for fps, width in LADDER:
            out = out_dir / f"{basename}.{kind}"
            encode_animated(ffmpeg, mp4, out, fps, width, kind, run=run)
            size = _size_of(out)
            if size and size <= max_bytes:
                warnings: tuple[str, ...] = ()
                if size > target_bytes:
                    warnings = (f"{kind} 超过目标体积 {target_bytes}B，实际 {size}B",)
                return Preview(path=out, kind=kind, byte_size=size, warnings=warnings)
            out.unlink(missing_ok=True)

    poster_size = _size_of(poster)
    return Preview(
        path=poster if poster.exists() else None,
        kind="png" if poster.exists() else None,
        byte_size=poster_size,
        warnings=(
            f"GIF 与 WebP 在全部降级档位下都超过硬上限 {max_bytes}B，已降级为海报帧",
        ),
    )
