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
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>.+)$', re.MULTILINE
)
EXCEPTION_RE = re.compile(
    r"^(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt)?): "
    r"(?P<message>.+)$",
    re.MULTILINE,
)

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


def parse_traceback(
    text: str, scene_file: str | Path
) -> tuple[str | None, str | None, int | None]:
    """Extract (exception type, message, line).

    Prefers the last frame inside the generated scene over library frames, so the
    reported line is one the model can actually edit.
    """
    frames = list(FRAME_RE.finditer(text or ""))
    if not frames:
        return None, None, None

    wanted = Path(str(scene_file)).name
    chosen = frames[-1]
    for frame in frames:
        if Path(frame.group("file")).name == wanted:
            chosen = frame

    exc_type: str | None = None
    message: str | None = None
    match = EXCEPTION_RE.search(text[chosen.end():])
    if match:
        exc_type = match.group("type")
        message = match.group("message").strip()
    return exc_type, message, int(chosen.group("line"))


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
    cleaned = strip_noise(stderr)
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
