"""The machine-precise half of the style contract.

The narrative half ("when to animate at all") lives in the Skill, which is only
loaded when it is relevant. This payload is what the model needs *while writing
code*: the exact palette, the font names that exist on this machine, the API traps
worth avoiding, and one skeleton it can adapt.
"""

from __future__ import annotations

from typing import Iterable

from .. import scenes, style
from . import envelope

API_NOTES = [
    "每个动画只讲一个想法；总时长控制在 8-20 秒。",
    "`self.play(...)` 的 `run_time` 默认 1.0 秒；收尾用 `self.wait(0.5)` 留出阅读时间。",
    "`.animate` 只能写成 `self.play(mob.animate.shift(...))`，不要先赋值再调用别的方法。",
    "数学内容用 `MathTex`；`Tex` 是文本模式，公式里的下划线与分数会报错。",
    "公式字符串请用原始字符串 `r\"...\"`，否则反斜杠会被 Python 吃掉。",
    "中文必须走 `cn()` 或用 `Text(..., font=FONT_CJK)`，否则会渲染成方框。",
    "图形默认按 `config.background_color` 反衬，直接用 `WHITE` 作正文颜色。",
    "避免自定义类与复杂继承：这段代码之后可能由模型自己读回来修改。",
]

SKELETON_BODY = '''

class Demo(Scene):
    def construct(self):
        heading = cn("核心结论", TITLE_SIZE, WHITE).to_edge(UP, buff=0.8)
        formula = MathTex(r"e^{i\\pi} + 1 = 0")
        formula.next_to(heading, DOWN, buff=0.8)
        ring = Circle(radius=1.1, color=C_BLUE).next_to(formula, DOWN, buff=0.7)

        self.play(Write(heading), run_time=PLAY_RUN_TIME)
        self.play(FadeIn(formula, shift=UP * 0.4), run_time=PLAY_RUN_TIME)
        self.play(Create(ring), run_time=PLAY_RUN_TIME)
        self.wait(TAIL_WAIT)
'''


def skeleton(cjk_font: str | None) -> str:
    """A paste-ready file: the preamble is embedded, so `cn` and the palette exist.

    Handing over a bare body would make the model paste code that dies with
    `NameError: name 'cn' is not defined`, so the guide ships the whole file.
    """
    from .. import style as style_mod

    return (
        "from manim import *\n\n"
        + style_mod.preamble(cjk_font)
        + SKELETON_BODY
    )


def style_guide_payload(
    cjk_font: str | None, fonts: Iterable[str] | None = None
) -> dict:
    facts = style.style_guide_facts(cjk_font, fonts)
    warnings: list[str] = []
    if cjk_font is None:
        warnings.append(
            "本机没有探测到可用的中文字体，中文可能显示为方框；"
            "请改用英文标签，或安装 Microsoft YaHei / SimHei。"
        )

    return envelope.plain_payload(
        palette=facts["palette"],
        typography=facts["typography"],
        pacing=facts["pacing"],
        cjkFont=cjk_font,
        availableCjkFonts=facts["availableCjkFonts"],
        apiNotes=list(API_NOTES),
        templates=scenes.catalogue(),
        skeleton=skeleton(cjk_font),
        warnings=warnings,
    )
