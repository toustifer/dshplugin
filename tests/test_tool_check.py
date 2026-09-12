"""check exists to make the cheap mistakes cheap, before a 10-second render."""

from manim_mcp.tools import check

GOOD = '''from manim import *


class Demo(Scene):
    def construct(self):
        self.play(Write(Text("hi")))
'''


def test_good_code_passes_with_the_scene_class_listed():
    result = check.check_code(GOOD)
    assert result["ok"] is True
    assert result["issues"] == []
    assert result["sceneClasses"] == ["Demo"]


def test_syntax_error_reports_the_line():
    result = check.check_code("from manim import *\nclass X(Scene)\n    pass\n")
    assert result["ok"] is False
    assert any("第 2 行" in issue for issue in result["issues"])


def test_missing_manim_import_is_reported():
    result = check.check_code("class Demo(Scene):\n    pass\n")
    assert result["ok"] is False
    assert any("from manim import *" in issue for issue in result["issues"])


def test_missing_scene_subclass_is_reported():
    result = check.check_code("from manim import *\n\nx = 1\n")
    assert result["ok"] is False
    assert any("Scene" in issue for issue in result["issues"])


def test_scene_without_construct_is_reported():
    result = check.check_code("from manim import *\n\n\nclass Demo(Scene):\n    pass\n")
    assert result["ok"] is False
    assert any("construct" in issue for issue in result["issues"])


def test_multiple_scene_classes_are_all_listed():
    code = (
        "from manim import *\n\n"
        "class A(Scene):\n    def construct(self):\n        pass\n\n"
        "class B(Scene):\n    def construct(self):\n        pass\n"
    )
    assert check.check_code(code)["sceneClasses"] == ["A", "B"]


def test_qualified_scene_base_is_recognised():
    code = (
        "import manim\n\n"
        "class Demo(manim.Scene):\n    def construct(self):\n        pass\n"
    )
    result = check.check_code(code)
    assert result["ok"] is True
    assert result["sceneClasses"] == ["Demo"]


def test_empty_code_is_reported():
    result = check.check_code("")
    assert result["ok"] is False
    assert any("空" in issue for issue in result["issues"])


def test_non_string_code_is_reported():
    result = check.check_code(None)
    assert result["ok"] is False


def test_suggested_scene_is_the_first_class():
    result = check.check_code(GOOD)
    assert result["suggestedScene"] == "Demo"
