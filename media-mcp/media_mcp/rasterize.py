"""Turn the first pages of a PDF into PNGs, so they can use the image channel.

Why not `<iframe>`: `/api/file` answers with `content-security-policy: sandbox;
default-src 'none'` — no `allow-*` tokens at all, so the document is a unique opaque
origin with plugins and scripts disabled, and the browser's PDF viewer does not render.

`pdftoppm` ships with MiKTeX, which this project already requires for Manim's LaTeX, so
this adds no new dependency. The cache directory is content-addressed: publishing the
same PDF twice converts once and cannot collide on a name.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from .config import Config

PAGE_RE = re.compile(r"-(\d+)\.png$")


def cache_dir(render_root: Path, pdf: Path) -> Path:
    digest = hashlib.sha1(pdf.read_bytes()).hexdigest()[:12]
    return render_root / "_pdf" / digest


def count_pages(pdf: Path, cfg: Config) -> int | None:
    """Total pages, via `pdfinfo` — which ships in the same MiKTeX bundle as `pdftoppm`.

    `pdftoppm` itself never reports a total, and rasterising every page just to count
    them would turn a 50-page report into 50 rendered pages of wasted work. `None` when
    the tool is missing or the output is not understood: the card simply omits the
    count rather than inventing one.
    """
    argv = [cfg.pdfinfo, str(pdf)]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in completed.stdout.splitlines():
        if line.lower().startswith("pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def rasterize(pdf: Path, cfg: Config) -> tuple[list[Path], int | None, list[str]]:
    """Return `(page_pngs, total_pages, warnings)`. Never raises: a broken converter or
    a corrupt PDF degrades the card, it does not fail the publish."""
    total = count_pages(pdf, cfg)
    target = cache_dir(cfg.render_root, pdf)
    cached = sorted(target.glob("page-*.png"))
    if cached:
        return cached, total, []

    target.mkdir(parents=True, exist_ok=True)
    prefix = target / "page"
    argv = [
        cfg.pdftoppm,
        "-png",
        "-r",
        str(cfg.pdf_dpi),
        "-f",
        "1",
        "-l",
        str(cfg.pdf_pages),
        str(pdf),
        str(prefix),
    ]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return [], total, [f"PDF 首页预览不可用（pdftoppm 调用失败: {cfg.pdftoppm}：{error}）"]

    pages = sorted(target.glob("page-*.png"))
    if not pages:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"退出码 {completed.returncode}"
        return [], total, [f"PDF 首页预览不可用（pdftoppm: {tail}）"]

    return pages, total, []
