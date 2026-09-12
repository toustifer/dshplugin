"""The model needs exact constants at write time, not a narrative."""

import ast

from manim_mcp.tools import style_guide


def test_payload_reports_the_local_cjk_font():
    payload = style_guide.style_guide_payload(cjk_font="SimHei", fonts=["SimHei", "Arial"])
    assert payload["ok"] is True
    assert payload["cjkFont"] == "SimHei"


def test_payload_warns_when_no_cjk_font_exists():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=["Arial"])
    assert payload["cjkFont"] is None
    assert any("中文" in note for note in payload["warnings"])


def test_palette_matches_the_style_module():
    from manim_mcp import style

    payload = style_guide.style_guide_payload(cjk_font=None, fonts=[])
    assert payload["palette"]["background"] == style.BACKGROUND
    assert payload["palette"]["highlight"] == style.HIGHLIGHT


def test_templates_are_listed_with_their_params():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=[])
    names = {row["name"] for row in payload["templates"]}
    assert names == {"equation", "graph", "diagram", "compare"}
    equation = [row for row in payload["templates"] if row["name"] == "equation"][0]
    assert "steps" in equation["params"]


def test_skeleton_is_valid_python_and_uses_the_cjk_helper():
    payload = style_guide.style_guide_payload(cjk_font="SimHei", fonts=["SimHei"])
    ast.parse(payload["skeleton"])
    assert "cn(" in payload["skeleton"]
    assert "from manim import *" in payload["skeleton"]


def test_skeleton_embeds_the_preamble_so_it_is_paste_ready():
    payload = style_guide.style_guide_payload(cjk_font="SimHei", fonts=["SimHei"])
    assert 'FONT_CJK = "SimHei"' in payload["skeleton"]
    assert "C_BLUE =" in payload["skeleton"]
    assert "TAIL_WAIT = 0.5" in payload["skeleton"]


def test_skeleton_without_a_font_still_compiles():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=["Arial"])
    compile(payload["skeleton"], "<skeleton>", "exec")
    assert "FONT_CJK = None" in payload["skeleton"]


def test_api_notes_mention_the_known_traps():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=[])
    blob = "\n".join(payload["apiNotes"])
    assert ".animate" in blob
    assert "MathTex" in blob
    assert "run_time" in blob
