"""Style constants and the CJK font picker, without importing Manim."""

from manim_mcp import style


def test_palette_matches_the_spec():
    assert style.BACKGROUND == "#0E1116"
    assert style.BLUE == "#58C4DD"
    assert style.HIGHLIGHT == "#FFD166"
    assert style.GREEN == "#7BE495"
    assert style.RED == "#FF6B6B"
    assert style.GREY == "#5A6472"


def test_detects_the_first_available_candidate():
    fonts = ["Arial", "SimHei", "Microsoft YaHei"]
    assert style.detect_cjk_font(fonts) == "Microsoft YaHei"


def test_falls_back_to_the_second_candidate():
    assert style.detect_cjk_font(["Arial", "SimHei"]) == "SimHei"


def test_matching_is_case_insensitive():
    assert style.detect_cjk_font(["MICROSOFT YAHEI"]) == "MICROSOFT YAHEI"


def test_returns_none_when_no_cjk_font_exists():
    assert style.detect_cjk_font(["Arial", "Times New Roman"]) is None


def test_loose_match_catches_families_not_in_the_candidate_list():
    assert style.detect_cjk_font(["Arial", "MSYH Custom"]) is None
    assert style.detect_cjk_font(["Arial", "Source Han Serif SC"]) == "Source Han Serif SC"


def test_empty_font_list_is_none():
    assert style.detect_cjk_font([]) is None


def test_preamble_declares_every_constant_and_the_helper():
    text = style.preamble("SimHei")
    assert 'config.background_color = "#0E1116"' in text
    assert 'C_BLUE = "#58C4DD"' in text
    assert 'C_HIGHLIGHT = "#FFD166"' in text
    assert 'C_GREEN = "#7BE495"' in text
    assert 'C_RED = "#FF6B6B"' in text
    assert 'C_GREY = "#5A6472"' in text
    assert 'FONT_CJK = "SimHei"' in text
    assert "def cn(" in text


def test_preamble_without_a_cjk_font_still_compiles():
    text = style.preamble(None)
    assert "FONT_CJK = None" in text
    compile(text, "<preamble>", "exec")


def test_preamble_with_a_font_compiles():
    compile(style.preamble("SimHei"), "<preamble>", "exec")


def test_preamble_emits_the_pacing_constants():
    text = style.preamble("SimHei")
    assert "PLAY_RUN_TIME = 1.0" in text
    assert "TAIL_WAIT = 0.5" in text
    assert "TITLE_SIZE = 44" in text


def test_style_guide_facts_reports_the_local_fonts():
    facts = style.style_guide_facts("SimHei", ["SimHei", "Arial", "SimSun"])
    assert facts["cjkFont"] == "SimHei"
    assert facts["availableCjkFonts"] == ["SimHei", "SimSun"]


def test_style_guide_facts_carries_the_palette_and_pacing():
    facts = style.style_guide_facts(None, [])
    assert facts["palette"]["background"] == "#0E1116"
    assert facts["typography"] == {"title": 44, "body": 32, "note": 24}
    assert facts["pacing"] == {"play_run_time": 1.0, "tail_wait": 0.5}


def test_list_fonts_never_raises():
    assert isinstance(style.list_fonts(), list)
