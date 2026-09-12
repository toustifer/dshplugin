"""The four declarative tools, plus the validation gate they share.

Validation runs before the run directory exists, so a malformed argument costs
nothing and leaves no debris in the gallery.
"""

from __future__ import annotations

from typing import Callable

from mcp.types import ImageContent, TextContent

from .. import config as config_mod
from .. import scenes
from ..engine import diagnostics, workspace
from . import envelope, pipeline

SUMMARY_BUILDERS: dict[str, Callable[[dict], dict]] = {
    "equation": lambda params: {"steps": len(params.get("steps") or [])},
    "graph": lambda params: {
        "expressions": len(params.get("expressions") or []),
        "parameter": bool(params.get("parameter")),
    },
    "diagram": lambda params: {
        "nodes": len(params.get("nodes") or []),
        "edges": len(params.get("edges") or []),
    },
    "compare": lambda params: {
        "leftItems": len((params.get("left") or {}).get("items") or []),
        "rightItems": len((params.get("right") or {}).get("items") or []),
    },
}


def run_template(
    cfg: config_mod.Config,
    template_name: str,
    *,
    quality: str,
    title: str | None,
    params: dict,
    render_fn: Callable | None = None,
    preview_fn: Callable | None = None,
) -> list[TextContent | ImageContent]:
    """Compile one template and render it."""
    try:
        scene_class, code = scenes.build(template_name, **params)
    except scenes.SceneSpecError as error:
        return _validation_failure(
            stage="validate", exception_type=type(error).__name__, message=str(error)
        )

    summary = SUMMARY_BUILDERS.get(template_name, lambda _: {})(params)

    return pipeline.execute(
        cfg,
        tool_name=template_name,
        code=code,
        scene_class=scene_class,
        quality=quality,
        title=title,
        args_summary=summary,
        run_id=workspace.new_run_id(),
        render_fn=render_fn,
        preview_fn=preview_fn,
    )


def _validation_failure(*, stage: str, exception_type: str, message: str):
    diagnostic = diagnostics.Diagnostic(stage=stage, type=exception_type, message=message)
    return envelope.content_blocks(
        envelope.failure_payload(run_id="", diagnostic=diagnostic)
    )
