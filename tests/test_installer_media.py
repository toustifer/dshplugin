"""Adding a second MCP and a second plugin must not break the byte-for-byte round trip
that is the whole safety argument for letting a script touch ~/.dsh."""

import json
import shutil
from pathlib import Path

import pytest

from dsh_installer import (
    MEDIA_BLOCK_ID,
    MEDIA_PACKAGE,
    Targets,
    apply_install,
    apply_uninstall,
    build_media_insert_block,
    plan_install,
)

GALLERY_PACKAGE = "dsh-manim-gallery"


@pytest.fixture()
def sandbox(tmp_path: Path):
    profile = tmp_path / "profile"
    (profile / "node_modules").mkdir(parents=True)
    (profile / "cordis.patch.yml").write_text("- id: connection\n  config: {}\n", encoding="utf-8")
    (profile / "package.json").write_text(
        json.dumps(
            {"name": "p", "private": True, "dsh": {"profile": {"bundles": []}}, "dependencies": {}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    source = tmp_path / "src"
    for package in (GALLERY_PACKAGE, MEDIA_PACKAGE):
        (source / package / "lib").mkdir(parents=True)
        if package == GALLERY_PACKAGE:
            (source / package / "lib" / "client.js").write_text(
                'const RENDER_ROOT = "D:/myprogram/dshplugin/renders";\n', encoding="utf-8"
            )
        else:
            (source / package / "lib" / "client.js").write_text("// client\n", encoding="utf-8")
        (source / package / "package.json").write_text("{}", encoding="utf-8")
    (source / "manim-mcp").mkdir()
    (source / "manim-mcp" / "server.py").write_text("# entry\n", encoding="utf-8")
    (source / "media-mcp").mkdir()
    (source / "media-mcp" / "server.py").write_text("# entry\n", encoding="utf-8")
    (source / "skills" / "manim-explainer").mkdir(parents=True)
    (source / "skills" / "manim-explainer" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    return Targets(
        profile_root=profile,
        plugin_root=tmp_path / "plugins",
        skill_root=tmp_path / "skills",
        source_root=source,
        render_root=tmp_path / "renders",
        python=r"D:\py\python.exe",
        manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe",
        pdftoppm=r"D:\miktex\pdftoppm.exe",
        pdfinfo=r"D:\miktex\pdfinfo.exe",
    )


def test_the_media_insert_block_mounts_the_mcp_under_its_own_id(sandbox):
    block = build_media_insert_block(sandbox)
    assert f"- id: {MEDIA_BLOCK_ID}" in block
    assert "serverName: media" in block
    assert "media-mcp" in block


def test_the_media_mcp_is_pinned_to_the_same_fs_cwd_as_the_overlay(sandbox):
    """One variable feeds both, so 'same drive' cannot drift into a silent 404."""
    block = build_media_insert_block(sandbox)
    assert sandbox.render_root.parent.as_posix() in block


def test_install_adds_both_plugins_and_both_mcp_rows(sandbox):
    apply_install(sandbox)
    patch = sandbox.patch_file.read_text(encoding="utf-8")
    assert "mcp-manim" in patch and MEDIA_BLOCK_ID in patch
    package = json.loads(sandbox.profile_package.read_text(encoding="utf-8"))
    assert MEDIA_PACKAGE in package["dsh"]["profile"]["bundles"]
    assert package["dependencies"][MEDIA_PACKAGE].startswith("link:")


def test_a_second_plan_reports_no_change(sandbox):
    apply_install(sandbox)
    assert plan_install(sandbox)["changed"] is False


def test_uninstall_restores_the_profile_byte_for_byte(sandbox):
    before_patch = sandbox.patch_file.read_text(encoding="utf-8")
    before_package = sandbox.profile_package.read_text(encoding="utf-8")
    apply_install(sandbox)
    apply_uninstall(sandbox)
    assert sandbox.patch_file.read_text(encoding="utf-8") == before_patch
    assert sandbox.profile_package.read_text(encoding="utf-8") == before_package
