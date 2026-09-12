"""stderr is the only ground truth after a failed render; parse it honestly."""

from pathlib import Path

from manim_mcp.engine import diagnostics

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCENE = Path(r"D:\myprogram\dshplugin\renders\20260912-153012-a1b2\scene.py")


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_strip_noise_removes_ansi_and_the_manim_runtime_warning():
    cleaned = diagnostics.strip_noise(read("manim_nameerror.txt"))
    assert "\x1b" not in cleaned
    assert "RuntimeWarning: 'manim.__main__'" not in cleaned
    assert "NameError: name 'Circle' is not defined" in cleaned


def test_strip_noise_removes_ansi_sequences():
    cleaned = diagnostics.strip_noise("\x1b[31mred\x1b[0m text\n")
    assert cleaned.strip() == "red text"


def test_strip_noise_removes_progress_lines():
    raw = "Rendering 12/40\nAnimation 3: Write\n12%|#   | 12/100\nreal content\n"
    cleaned = diagnostics.strip_noise(raw)
    assert "real content" in cleaned
    assert "12%|" not in cleaned


def test_parse_finds_the_frame_in_the_scene_file():
    exc_type, message, line = diagnostics.parse_traceback(
        diagnostics.strip_noise(read("manim_nameerror.txt")), SCENE
    )
    assert exc_type == "NameError"
    assert message == "name 'Circle' is not defined"
    assert line == 9


def test_parse_prefers_the_scene_file_over_library_frames():
    exc_type, _, line = diagnostics.parse_traceback(
        diagnostics.strip_noise(read("manim_latex_error.txt")), SCENE
    )
    assert exc_type == "RuntimeError"
    assert line == 6


def test_parse_without_a_scene_frame_falls_back_to_the_last_one():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "C:\\lib\\a.py", line 3, in go\n'
        "    raise ValueError('x')\n"
        "ValueError: x\n"
    )
    assert diagnostics.parse_traceback(raw, SCENE) == ("ValueError", "x", 3)


def test_parse_returns_nothing_when_there_is_no_traceback():
    assert diagnostics.parse_traceback("just some noise\n", SCENE) == (None, None, None)


def test_classify_reads_the_offending_source_line(tmp_path: Path):
    scene = tmp_path / "scene.py"
    scene.write_text(
        "from manim import *\n"
        "\n"
        "class Smoke(Scene):\n"
        "    def construct(self):\n"
        "        circle = Circle(radius=1)\n",
        encoding="utf-8",
    )
    raw = read("manim_nameerror.txt").replace(str(SCENE), str(scene)).replace(
        "line 9", "line 5"
    )
    result = diagnostics.classify(raw, scene, stage="manim")
    assert result.stage == "manim"
    assert result.type == "NameError"
    assert result.line == 5
    assert result.source_line == "circle = Circle(radius=1)"
    assert "from manim import *" in result.hint


def test_classify_tolerates_a_missing_scene_file(tmp_path: Path):
    result = diagnostics.classify(read("manim_nameerror.txt"), tmp_path / "gone.py")
    assert result.source_line is None


def test_hint_for_nameerror_names_the_missing_symbol():
    hint = diagnostics.hint_for("NameError", "name 'Circle' is not defined", "")
    assert "Circle" in hint
    assert "from manim import *" in hint


def test_hint_for_nameerror_without_a_symbol_still_helps():
    hint = diagnostics.hint_for("NameError", "something went wrong", "")
    assert "from manim import *" in hint


def test_hint_for_latex_failure():
    hint = diagnostics.hint_for(
        "RuntimeError", "latex failed but did not produce a log file.", "LaTeX Error"
    )
    assert "LaTeX" in hint
    assert "MathTex" in hint


def test_hint_for_animate_misuse():
    hint = diagnostics.hint_for(
        "AttributeError",
        "'Circle' object has no attribute 'shift'",
        "ValueError: Please use ... .animate syntax",
    )
    assert ".animate" in hint


def test_hint_for_missing_latex_binary():
    hint = diagnostics.hint_for(
        "FileNotFoundError", "[Errno 2] No such file or directory: 'latex'", ""
    )
    assert "MiKTeX" in hint


def test_hint_for_font_problem():
    hint = diagnostics.hint_for("ValueError", "font 'Nope' not found", "")
    assert "字体" in hint


def test_hint_for_unpack_error():
    hint = diagnostics.hint_for(
        "ValueError", "too many values to unpack (expected 2)", ""
    )
    assert "参数" in hint


def test_hint_is_none_for_an_unrecognised_failure():
    assert diagnostics.hint_for("KeyError", "42", "") is None


def test_tail_keeps_the_end_and_marks_truncation():
    tail = diagnostics.tail("x" * 100, max_chars=10)
    assert tail.endswith("x" * 10)
    assert "100" in tail
    assert diagnostics.tail("short", max_chars=100) == "short"


def test_as_dict_omits_absent_fields():
    payload = diagnostics.Diagnostic(stage="timeout").as_dict()
    assert payload["stage"] == "timeout"
    assert "type" not in payload
    assert payload["stderrTail"] == ""


def test_as_dict_uses_camel_case_for_the_source_line():
    payload = diagnostics.Diagnostic(
        stage="manim", line=5, source_line="x = 1", hint="加 import"
    ).as_dict()
    assert payload["sourceLine"] == "x = 1"
    assert "source_line" not in payload
    assert payload["hint"] == "加 import"


def test_classify_without_a_traceback_still_reports_stderr():
    result = diagnostics.classify("boom\n", SCENE, stage="manim")
    assert result.type is None
    assert result.hint is None
    assert "boom" in result.stderr_tail
