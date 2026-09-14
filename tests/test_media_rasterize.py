"""PDF cannot be shown in an <iframe>: /api/file answers with
`content-security-policy: sandbox; default-src 'none'`, so the browser's PDF viewer
never renders. Rasterising to PNG reuses the image channel that already works."""

import subprocess
from pathlib import Path

import pytest

from media_mcp.config import load_config
from media_mcp.rasterize import cache_dir, rasterize


@pytest.fixture()
def cfg(tmp_path: Path):
    renders = tmp_path / "renders"
    renders.mkdir()
    return load_config(
        env={
            "MEDIA_MCP_ROOTS": str(tmp_path),
            "MEDIA_MCP_FS_CWD": str(tmp_path),
            "MEDIA_MCP_PDF_PAGES": "3",
            "MEDIA_MCP_PDF_DPI": "72",
        }
    )


def test_cache_dir_is_content_addressed(tmp_path: Path, cfg):
    first = tmp_path / "a.pdf"
    first.write_bytes(b"%PDF-1.7\nsame")
    second = tmp_path / "b.pdf"
    second.write_bytes(b"%PDF-1.7\nsame")
    other = tmp_path / "c.pdf"
    other.write_bytes(b"%PDF-1.7\ndifferent")
    assert cache_dir(cfg.render_root, first) == cache_dir(cfg.render_root, second)
    assert cache_dir(cfg.render_root, first) != cache_dir(cfg.render_root, other)


def test_a_missing_pdftoppm_is_not_fatal_and_is_reported(tmp_path: Path, cfg):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    broken = load_config(
        env={
            "MEDIA_MCP_ROOTS": str(tmp_path),
            "MEDIA_MCP_FS_CWD": str(tmp_path),
            "MEDIA_MCP_PDFTOPPM": "definitely-not-a-real-binary",
            "MEDIA_MCP_PDFINFO": "definitely-not-a-real-binary",
        }
    )
    pages, total, warnings = rasterize(pdf, broken)
    assert pages == []
    assert total is None
    assert any("pdftoppm" in w for w in warnings)


def test_a_corrupt_pdf_is_not_fatal(tmp_path: Path, cfg):
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"not a pdf at all")
    pages, total, warnings = rasterize(pdf, cfg)
    assert pages == []
    assert warnings


@pytest.mark.skipif(
    subprocess.run(["pdftoppm", "-v"], capture_output=True).returncode not in (0, 1),
    reason="pdftoppm is not installed",
)
def test_a_real_pdf_becomes_pngs(tmp_path: Path, cfg):
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "minimal.pdf"
    pages, total, warnings = rasterize(fixture, cfg)
    assert pages, f"no page produced; warnings={warnings}"
    assert pages[0].suffix == ".png"
    assert pages[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert total == 1


def test_the_page_cap_is_honoured(tmp_path: Path, cfg):
    """A 50-page PDF must not become 50 images in the conversation."""
    assert cfg.pdf_pages == 3


def test_the_total_page_count_comes_from_pdfinfo(tmp_path: Path, cfg, monkeypatch):
    """`pdftoppm` never reports a total; inventing one would show "共 1 页" on a report."""
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(
        "media_mcp.rasterize.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="Pages:          12\n", stderr=""),
    )
    from media_mcp.rasterize import count_pages

    assert count_pages(pdf, cfg) == 12


def test_an_unreadable_pdfinfo_output_yields_no_count(tmp_path: Path, cfg, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(
        "media_mcp.rasterize.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="boom"),
    )
    from media_mcp.rasterize import count_pages

    assert count_pages(pdf, cfg) is None
