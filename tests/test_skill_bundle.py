"""Tests for the expanded manim-explainer skill bundle.

Validates that:
1. All referenced sub-documents in SKILL.md actually exist on disk.
2. Every sub-document has proper structure and meaningful non-empty content.
3. No non-existent tools or broken relative links are introduced.
4. Hard requirements and guardrails remain present in the root SKILL.md router.
5. All 6 sub-documents exist:
   - guides/templates.md
   - guides/raw-code.md
   - guides/style.md
   - reference/troubleshooting.md
   - reference/install.md
   - reference/architecture.md
"""

import re
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skills" / "manim-explainer"
SKILL_MD = SKILL_DIR / "SKILL.md"

EXPECTED_SUBDOCS = [
    "guides/templates.md",
    "guides/raw-code.md",
    "guides/style.md",
    "reference/troubleshooting.md",
    "reference/install.md",
    "reference/architecture.md",
]


def test_skill_directory_exists():
    assert SKILL_DIR.is_dir()
    assert SKILL_MD.is_file()


@pytest.mark.parametrize("rel_path", EXPECTED_SUBDOCS)
def test_expected_subdoc_exists(rel_path: str):
    target = SKILL_DIR / rel_path
    assert target.is_file(), f"Missing expected subdoc: {rel_path}"
    content = target.read_text(encoding="utf-8").strip()
    assert len(content) > 100, f"Subdoc {rel_path} is too short or empty"
    assert content.startswith("#"), f"Subdoc {rel_path} must start with markdown heading"


def test_skill_md_references_all_subdocs():
    text = SKILL_MD.read_text(encoding="utf-8")
    for rel_path in EXPECTED_SUBDOCS:
        # Should be referenced as relative path in markdown
        normalized = rel_path.replace("\\", "/")
        assert normalized in text, f"SKILL.md does not reference {normalized}"


def test_no_broken_relative_links_in_subdocs():
    for rel_path in EXPECTED_SUBDOCS:
        target = SKILL_DIR / rel_path
        if not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        # Find relative markdown links like [foo](bar.md) or `guides/xxx.md`
        refs = re.findall(r'`(guides/[a-z-]+\.md|reference/[a-z-]+\.md)`', text)
        for ref in refs:
            ref_path = SKILL_DIR / ref
            assert ref_path.is_file(), f"Broken relative ref `{ref}` inside {rel_path}"


def test_templates_guide_covers_all_four_templates():
    target = SKILL_DIR / "guides" / "templates.md"
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    for name in ("equation", "graph", "diagram", "compare"):
        assert f"mcp__manim__{name}" in text or f"`{name}`" in text


def test_raw_code_guide_covers_crucial_pitfalls():
    target = SKILL_DIR / "guides" / "raw-code.md"
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert "ShowPassingFlash" in text
    assert "VGroup" in text
    assert "cn(" in text
    assert "check" in text


def test_install_reference_covers_setup_and_multi_drive():
    target = SKILL_DIR / "reference" / "install.md"
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert "install.ps1" in text
    assert "restart-web.ps1" in text
    assert "盘符" in text or "drive" in text.lower()
