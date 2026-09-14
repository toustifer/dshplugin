"""Every environment read happens here.

Nothing else in this package touches `os.environ`, so `doctor()` can report the whole
runtime contract in one place and tests can construct a `Config` directly.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# parents[2] of media-mcp/media_mcp/config.py is the repository root.
DEFAULT_RENDER_ROOT = Path(__file__).resolve().parents[2] / "renders"
DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # matches the shipped /api/file cap
DEFAULT_PDF_PAGES = 3
DEFAULT_PDF_DPI = 110


def _positive_int(env: dict[str, str], name: str, fallback: int) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return fallback
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _path_list(env: dict[str, str], name: str, fallback: Path) -> tuple[Path, ...]:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return (fallback,)
    parts = [Path(part.strip()) for part in raw.split(";") if part.strip()]
    if not parts:
        raise ValueError(f"{name} listed no usable path")
    return tuple(parts)


@dataclass(frozen=True)
class Config:
    roots: tuple[Path, ...]
    fs_cwd: Path
    max_bytes: int
    pdf_pages: int
    pdf_dpi: int
    render_root: Path
    pdftoppm: str
    pdfinfo: str
    python: str

    def doctor(self) -> dict:
        return {
            "python": self.python,
            "pdftoppm": self.pdftoppm,
            "pdfinfo": self.pdfinfo,
            "renderRoot": self.render_root.as_posix(),
            "fsCwd": self.fs_cwd.as_posix(),
            "roots": [path.as_posix() for path in self.roots],
            "maxBytes": self.max_bytes,
            "pdfPages": self.pdf_pages,
            "pdfDpi": self.pdf_dpi,
            "pdftoppmFound": shutil.which(self.pdftoppm) is not None
            or Path(self.pdftoppm).exists(),
            "pdfinfoFound": shutil.which(self.pdfinfo) is not None
            or Path(self.pdfinfo).exists(),
        }


def load_config(env: dict[str, str] | None = None) -> Config:
    source = dict(os.environ if env is None else env)
    render_root = DEFAULT_RENDER_ROOT
    root = render_root.parent
    return Config(
        roots=_path_list(source, "MEDIA_MCP_ROOTS", root),
        # DEFAULT is the same expression the installer pins, so the two cannot drift.
        fs_cwd=Path(source.get("MEDIA_MCP_FS_CWD") or root),
        max_bytes=_positive_int(source, "MEDIA_MCP_MAX_BYTES", DEFAULT_MAX_BYTES),
        pdf_pages=_positive_int(source, "MEDIA_MCP_PDF_PAGES", DEFAULT_PDF_PAGES),
        pdf_dpi=_positive_int(source, "MEDIA_MCP_PDF_DPI", DEFAULT_PDF_DPI),
        render_root=render_root,
        pdftoppm=source.get("MEDIA_MCP_PDFTOPPM") or "pdftoppm",
        pdfinfo=source.get("MEDIA_MCP_PDFINFO") or "pdfinfo",
        python=source.get("MEDIA_MCP_PYTHON") or sys.executable,
    )
