"""One palette and one CJK font decision, shared by every generated scene.

Templates never hard-code a colour or a font name: they call `preamble()` and use
the constants it emits, so the look stays consistent and a font that is missing on
this machine degrades to a warning instead of a scene full of tofu boxes.
"""

from __future__ import annotations

import json
from typing import Iterable

BACKGROUND = "#0E1116"
BLUE = "#58C4DD"
HIGHLIGHT = "#FFD166"
GREEN = "#7BE495"
RED = "#FF6B6B"
GREY = "#5A6472"
# Axes and box outlines read fine in GREY because they are thick and closed. A
# thin arrow on #0E1116 does not: at 3px the grey disappears into the background,
# so edges get their own lighter step.
EDGE = "#8A94A6"

TITLE_SIZE = 44
BODY_SIZE = 32
NOTE_SIZE = 24
PLAY_RUN_TIME = 1.0
TAIL_WAIT = 0.5

# Ordered by preference. Manim's Text() takes a family name resolved by Pango, so
# a family that is not installed renders as boxes rather than raising — hence the
# detection step instead of trusting a default.
CJK_FONT_CANDIDATES = (
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "SimSun",
)

LOOSE_CJK_MARKERS = ("YaHei", "SimHei", "SimSun", "Noto Sans CJK", "Source Han")

PALETTE = {
    "background": BACKGROUND,
    "blue": BLUE,
    "highlight": HIGHLIGHT,
    "green": GREEN,
    "red": RED,
    "grey": GREY,
    "edge": EDGE,
}


def list_fonts() -> list[str]:
    """Every font family Pango can see. Empty when Manim is not importable."""
    try:
        import manimpango
    except ImportError:
        return []
    try:
        return [str(name) for name in manimpango.list_fonts()]
    except Exception:  # pragma: no cover - a broken font cache must not kill the server
        return []


def detect_cjk_font(fonts: Iterable[str] | None = None) -> str | None:
    """Pick a CJK-capable family, preferring the documented order."""
    available = list(fonts) if fonts is not None else list_fonts()
    by_case = {name.casefold(): name for name in available}

    for candidate in CJK_FONT_CANDIDATES:
        hit = by_case.get(candidate.casefold())
        if hit is not None:
            return hit

    for name in available:
        if any(marker.casefold() in name.casefold() for marker in LOOSE_CJK_MARKERS):
            return name

    return None


def _literal(value: str | None) -> str:
    if value is None:
        return "None"
    return json.dumps(value, ensure_ascii=False)


def python_literal(value) -> str:
    """A **Python** source literal for `value`.

    `json.dumps` is the tempting shortcut and is wrong for three values: it emits
    `null`, `true`, and `false`, which Python parses as ordinary identifiers and
    only rejects with `NameError` when Manim imports the generated file. That is
    a failure an `ast.parse` assertion cannot see, so every template must route
    its literals through here.
    """
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    return json.dumps(value, ensure_ascii=False)


def preamble(cjk_font: str | None) -> str:
    """Header source that every generated scene starts with.

    Emits the palette, the sizes, the pacing constants, and `cn()` — the only
    text helper templates are allowed to use for prose, so Chinese never falls
    back to a Latin-only family.
    """
    return f'''config.background_color = {_literal(BACKGROUND)}
C_BLUE = {_literal(BLUE)}
C_HIGHLIGHT = {_literal(HIGHLIGHT)}
C_GREEN = {_literal(GREEN)}
C_RED = {_literal(RED)}
C_GREY = {_literal(GREY)}
C_EDGE = {_literal(EDGE)}

TITLE_SIZE = {TITLE_SIZE}
BODY_SIZE = {BODY_SIZE}
NOTE_SIZE = {NOTE_SIZE}
PLAY_RUN_TIME = {PLAY_RUN_TIME}
TAIL_WAIT = {TAIL_WAIT}

FONT_CJK = {_literal(cjk_font)}


def cn(text, size=BODY_SIZE, color=WHITE, weight=NORMAL):
    """Text with a CJK-capable family when one exists on this machine."""
    if FONT_CJK is None:
        return Text(text, font_size=size, color=color, weight=weight)
    return Text(text, font=FONT_CJK, font_size=size, color=color, weight=weight)
'''


def style_guide_facts(cjk_font: str | None, fonts: Iterable[str] | None = None) -> dict:
    """The machine-precise half of `style_guide`; the narrative lives in SKILL.md."""
    available = list(fonts) if fonts is not None else list_fonts()
    return {
        "palette": dict(PALETTE),
        "typography": {"title": TITLE_SIZE, "body": BODY_SIZE, "note": NOTE_SIZE},
        "pacing": {"play_run_time": PLAY_RUN_TIME, "tail_wait": TAIL_WAIT},
        "cjkFont": cjk_font,
        "availableCjkFonts": [
            name for name in available if detect_cjk_font([name]) == name
        ],
    }
