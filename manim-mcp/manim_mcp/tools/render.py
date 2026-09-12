"""The escape hatch: render whatever Manim code the model wrote.

`check` runs first so a syntax error or a missing `construct` is answered in
milliseconds rather than after a Manim process start.
"""

from __future__ import annotations

from typing import Callable

from mcp.types import ImageContent, TextContent

from .. import config as config_mod
from ..engine import diagnostics, workspace
from . import check as check_tool
from . import envelope, pipeline


def run_code(
    cfg: config_mod.Config,
    *,
    code: str,
    scene_name: str | None,
    quality: str,
    render_fn: Callable | None = None,
    preview_fn: Callable | None = None,
) -> list[TextContent | ImageContent]:
    """Validate, then render, raw Manim source."""
    verdict = check_tool.check_code(code)
    if not verdict["ok"]:
        return envelope.content_blocks(
            envelope.failure_payload(
                run_id="",
                diagnostic=diagnostics.Diagnostic(
                    stage="validate",
                    type="InvalidScene",
                    message="；".join(verdict["issues"]),
                ),
            )
        )

    available = verdict["sceneClasses"]
    chosen = scene_name or verdict.get("suggestedScene")
    if chosen not in available:
        return envelope.content_blocks(
            envelope.failure_payload(
                run_id="",
                diagnostic=diagnostics.Diagnostic(
                    stage="validate",
                    type="UnknownScene",
                    message=(
                        f"代码里没有名为 {chosen!r} 的场景类；"
                        f"可用的是：{', '.join(available)}"
                    ),
                ),
            )
        )

    return pipeline.execute(
        cfg,
        tool_name="render",
        code=code,
        scene_class=chosen,
        quality=quality,
        title=None,
        args_summary={"lines": len(code.splitlines())},
        run_id=workspace.new_run_id(),
        render_fn=render_fn,
        preview_fn=preview_fn,
    )
