"""Turn raw subprocess stderr into one actionable Diagnostic.

A failed render is only useful to the model if it can act on it, so the goal is
never to forward a blob: it is to name the exception, the line in *its own* file,
that line's source, and the specific edit that most often fixes it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
RUNTIME_WARNING_RE = re.compile(
    r"^.*RuntimeWarning: 'manim\.__main__'.*(?:\n\s+.*)*$", re.MULTILINE
)
PROGRESS_RE = re.compile(
    r"^\s*(?:Rendering\s|Animation\s|Playing\s|\d+%\|).*$", re.MULTILINE
)
FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+)",? +line (?P<line>\d+),? +in (?P<func>.+?)\s*$',
    re.MULTILINE,
)
# A rich panel right-pads every line, and the padding collides with the space
# that follows the comma, so a *wrapped* frame loses that comma entirely:
#     │ D:\...\scene.p │
#     │ y:6 in construct │
# The break lands mid-extension, so the fragment is not a whole character.
PANEL_FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+?)"'
    r'(?:,? +line (?P<closed_line>\d+),? +in (?P<closed_func>.+?))?'
    r'(?P<open>: *\d+ +in +.+?)?\s*$'
)
# The leading half of a wrapped frame: a path cut mid-extension.
FRAME_FRAGMENT_RE = re.compile(r"^[A-Za-z]:.+[.\\/][A-Za-z]?$")
# The trailing half: the rest of the path, then `:NN in func`. The rest of the
# path here is always exactly one character ("y" from "scene.p" + "y").
FRAME_CONTINUATION_RE = re.compile(
    r"^(?P<rest>\S):(?P<line>\d+) +in +(?P<func>\S.*?)\s*$"
)
ANCHORED_FRAME_RE = re.compile(
    r'^File "(?P<file>.+?)":(?P<line>\d+) +in +(?P<func>.+)$'
)
EXCEPTION_RE = re.compile(
    r"^(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt)?): "
    r"(?P<message>.+)$",
    re.MULTILINE,
)
# Manim 0.20.1 does not print a plain traceback: `error_console.print_exception()`
# draws a rich panel, right-pads every line, and wraps long paths onto a second
# line. Every frame line therefore fails FRAME_RE unless the panel is undone first.
PANEL_BORDER_RE = re.compile(r"^[\u2500-\u257F]+$")
# The panel's top edge is a rule with the title embedded in it, so it is not
# purely box-drawing characters.
PANEL_HEADER_RE = re.compile(r"^[\u2500-\u257F]+\s*Traceback.*$")
PANEL_EDGE_RE = re.compile(r"^[\u2502\u2503]\s?|\s*[\u2502\u2503]$")

DEFAULT_TAIL_CHARS = 4000


@dataclass(frozen=True)
class Diagnostic:
    """What went wrong, where, and what to try instead."""

    stage: str
    type: str | None = None
    message: str | None = None
    line: int | None = None
    source_line: str | None = None
    hint: str | None = None
    stderr_tail: str = ""

    def as_dict(self) -> dict:
        payload: dict = {"stage": self.stage}
        for key, value in (
            ("type", self.type),
            ("message", self.message),
            ("line", self.line),
            ("sourceLine", self.source_line),
            ("hint", self.hint),
        ):
            if value is not None:
                payload[key] = value
        payload["stderrTail"] = self.stderr_tail
        return payload


def strip_noise(text: str) -> str:
    """Drop ANSI, progress rows, and the harmless runpy warning."""
    cleaned = ANSI_RE.sub("", text or "")
    cleaned = RUNTIME_WARNING_RE.sub("", cleaned)
    cleaned = PROGRESS_RE.sub("", cleaned)
    return cleaned


def tail(text: str, max_chars: int = DEFAULT_TAIL_CHARS) -> str:
    """The end of a long log, with an explicit marker when it was cut."""
    body = text or ""
    if len(body) <= max_chars:
        return body
    return f"...[{len(body)} chars truncated]...\n{body[-max_chars:]}"


def _frame_parts(line: str) -> dict | None:
    """Split a frame line into its pieces, tolerating a mid-path wrap.

    Returns `{file, line, func, fragment?}`. A `fragment` means the line holds
    only half of a wrapped frame; a plain traceback never produces one, so this
    cannot misfire on clean input.
    """
    match = PANEL_FRAME_RE.match(line)
    if match is not None:
        file = match.group("file")
        if match.group("closed_line") is not None:
            return {
                "file": file,
                "line": int(match.group("closed_line")),
                "func": match.group("closed_func"),
            }
        if match.group("open") is not None:
            number, _, func = match.group("open").lstrip(":").partition(" in ")
            return {"file": file, "line": int(number.strip()), "func": func.strip()}
        if FRAME_FRAGMENT_RE.match(file):
            return {"file": file, "fragment": True}
        return None

    # No `File "` marker at all: either the leading half of a wrapped frame, or
    # the trailing half that rich already stripped the marker from.
    if FRAME_FRAGMENT_RE.match(line):
        return {"file": line, "fragment": True}
    continuation = FRAME_CONTINUATION_RE.match(line)
    if continuation is not None:
        return {
            "rest": continuation.group("rest"),
            "line": int(continuation.group("line")),
            "func": continuation.group("func"),
        }
    return None


def _to_frame(line: str) -> tuple[str, int, str] | None:
    """The (file, line, func) triple of a complete frame line, or None."""
    # The canonical rewrite is checked first: it is exactly what unwrap_panels
    # leaves behind, so this stays cheap and unambiguous for already-good input.
    anchored = ANCHORED_FRAME_RE.match(line)
    if anchored is not None:
        return (
            anchored.group("file"),
            int(anchored.group("line")),
            anchored.group("func"),
        )
    parts = _frame_parts(line)
    if parts is None or "fragment" in parts or "rest" in parts:
        return None
    return parts["file"], parts["line"], parts["func"]


def unwrap_panels(text: str) -> str:
    """Undo rich's bordered panels so the traceback reads like plain text.

    Two transformations are needed, and both matter: dropping the box-drawing
    borders, and putting a frame line back together after rich broke it, because
    the wrapped path does not fit the panel width. `scene.p` + `y:6 in construct`
    has to become one `File ".../scene.py", line 6, in construct`, or the
    scene-file frame cannot be recognised at all -- which is exactly what happened
    to every real failure before this.

    Nothing here guesses from line shapes: a line is only rewritten when it
    actually parses as a frame, so a plain traceback passes through untouched.
    """
    materialised: list[str] = []
    for raw in (text or "").splitlines():
        line = PANEL_EDGE_RE.sub("", raw).strip()
        if PANEL_BORDER_RE.match(line) or PANEL_HEADER_RE.match(line):
            materialised.append("")
            continue

        parts = _frame_parts(line)
        if parts is not None and "rest" in parts and materialised:
            # The previous line only looked complete because rich padded it and
            # swallowed the opening `File "`; it is really this frame's front half.
            previous = _frame_parts(materialised[-1]) if materialised[-1] else None
            if previous is not None and "fragment" in previous:
                materialised[-1] = (
                    f'File "{previous["file"]}{parts["rest"]}", '
                    f'line {parts["line"]}, in {parts["func"]}'
                )
                continue
        materialised.append(line)
    return "\n".join(materialised)


def parse_traceback(
    text: str, scene_file: str | Path
) -> tuple[str | None, str | None, int | None]:
    """Extract (exception type, message, line).

    Prefers the last frame inside the generated scene over library frames, so the
    reported line is one the model can actually edit.
    """
    frames = [
        (index, frame)
        for index, frame in enumerate(map(_to_frame, (text or "").splitlines()))
        if frame
    ]
    if not frames:
        return None, None, None

    wanted = Path(str(scene_file)).name
    chosen_index, chosen = frames[-1]
    for index, frame in frames:
        if Path(frame[0]).name == wanted:
            chosen_index, chosen = index, frame

    exc_type: str | None = None
    message: str | None = None
    # Never anchored to a line start: inside a panel the exception is followed by
    # the box edge, so it never sits at column 0.
    match = EXCEPTION_RE.search("\n".join((text or "").splitlines()[chosen_index:]))
    if match is None:
        match = EXCEPTION_RE.search(text or "")
    if match:
        exc_type = match.group("type")
        message = match.group("message").strip()
    return exc_type, message, chosen[1]


def _source_line(scene_file: str | Path, line: int | None) -> str | None:
    if line is None:
        return None
    try:
        lines = Path(scene_file).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()
    return None


def hint_for(exception_type: str | None, message: str | None, blob: str) -> str | None:
    """The single most likely fix, or None when the failure is unfamiliar.

    Rules read one combined haystack: the same phrase can land in the exception
    message or in the surrounding log depending on which layer raised, and a rule
    that only looked at one of them would miss half its cases.
    """
    etype = (exception_type or "").casefold()
    text = (message or "").casefold()
    haystack = f"{text}\n{(blob or '').casefold()}"

    if etype.endswith("nameerror"):
        match = re.search(r"name '([^']+)'", message or "")
        symbol = match.group(1) if match else "该名字"
        return (
            f"`{symbol}` 未定义。生成的代码开头需要 `from manim import *`；"
            "如果这是你自己命名的变量，检查它是否在使用之前就完成了赋值。"
        )

    if "latex" in haystack and (
        "latex error" in haystack or "did not produce a log file" in haystack
    ):
        return (
            "LaTeX 编译失败：检查公式里的反斜杠转义是否在 Python 字符串里被吃掉，"
            "避免使用未安装宏包提供的命令，并确认数学内容用的是 `MathTex` 而不是 `Tex`。"
        )

    if etype.endswith("filenotfounderror") and (
        "latex" in haystack or "dvisvgm" in haystack
    ):
        return "找不到 LaTeX 工具链：确认 MiKTeX 已安装，且 `latex` 与 `dvisvgm` 在 PATH 上。"

    if etype.endswith("attributeerror") and ".animate" in haystack:
        return (
            "`.animate` 用法有误：写成 `mob.animate.shift(...)`，"
            "并把这个表达式整体作为 `self.play(...)` 的参数，不要把它先赋值再调用别的方法。"
        )

    if "font" in haystack and ("not found" in haystack or "unavailable" in haystack):
        return "字体不可用：改用 `style_guide` 返回的本机中文字体名，或直接使用 `cn()` 辅助函数。"

    if etype.endswith("valueerror") and "too many values to unpack" in text:
        return "Mobject 构造参数个数不对：检查该图形类的必填参数数量。"

    return None


def classify(stderr: str, scene_file: str | Path, stage: str = "manim") -> Diagnostic:
    """One pass from raw stderr to a Diagnostic."""
    cleaned = unwrap_panels(strip_noise(stderr))
    exc_type, message, line = parse_traceback(cleaned, scene_file)
    return Diagnostic(
        stage=stage,
        type=exc_type,
        message=message,
        line=line,
        source_line=_source_line(scene_file, line),
        hint=hint_for(exc_type, message, cleaned),
        stderr_tail=tail(cleaned),
    )
