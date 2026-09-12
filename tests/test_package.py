"""The package must import from a bare checkout, with no install step."""

import manim_mcp


def test_version_is_declared():
    assert isinstance(manim_mcp.__version__, str)
    assert manim_mcp.__version__.strip() != ""
