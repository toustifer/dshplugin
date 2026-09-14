"""The reference form was measured, not reasoned: `node:path.resolve` keeps only the
cwd's DRIVE for a `/`-rooted argument, so the reference is the absolute path minus the
drive letter. Getting this wrong is a silent 404 in the conversation."""

from pathlib import Path

import pytest

from media_mcp.reference import reference_for, rooted_reference


def test_the_drive_letter_is_dropped_and_every_directory_is_kept():
    assert rooted_reference("D:/a/b/c.mp4") == "/a/b/c.mp4"


def test_a_posix_absolute_path_is_already_the_reference():
    assert rooted_reference("/srv/a/b.mp4") == "/srv/a/b.mp4"


@pytest.mark.parametrize("bad", ["//server/share/a.mp4", "relative/a.mp4", "", "C:"])
def test_forms_with_no_same_origin_meaning_are_refused(bad: str):
    assert rooted_reference(bad) is None


@pytest.mark.parametrize("bad", ["a b.mp4", "a(b).mp4", "中文.mp4"])
def test_characters_that_break_markdown_or_urls_are_refused(bad: str):
    assert rooted_reference(f"/x/{bad}") is None


def test_reference_for_resolves_a_real_path(tmp_path: Path):
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"x")
    reference = reference_for(target)
    assert reference is not None
    assert reference.endswith("/clip.mp4")
    assert ":" not in reference


def test_reference_for_refuses_a_relative_path():
    assert reference_for(Path("clip.mp4")) is None
