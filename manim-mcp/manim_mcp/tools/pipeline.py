"""The single side-effecting path: render, preview, record, report.

Both the declarative tools and the raw-code escape hatch end here, so the run
layout, the index entry, the warning policy, and the content blocks are identical
no matter which tool the model picked.

A render that succeeds is never reported as a failure just because a *secondary*
step (index write, pruning) went wrong; those become warnings instead.
"""

from __future__ import annotations

import datetime as _datetime
from pathlib import Path
from typing import Callable

from mcp.types import ImageContent, TextContent

from .. import config as config_mod
from ..engine import index, postprocess, render, workspace
from . import envelope


def _iso_now() -> str:
    return _datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _prune_and_reconcile(cfg: config_mod.Config, run_id: str) -> list[str]:
    """Retention, then drop the index entries of whatever was removed."""
    removed = workspace.prune_runs(cfg.render_root, cfg.keep_runs)
    for gone in removed:
        if gone != run_id:
            index.remove_run(cfg.render_root, gone)
    return removed


def execute(
    cfg: config_mod.Config,
    *,
    tool_name: str,
    code: str,
    scene_class: str,
    quality: str,
    title: str | None,
    args_summary: dict,
    run_id: str,
    render_fn: Callable | None = None,
    preview_fn: Callable | None = None,
) -> list[TextContent | ImageContent]:
    """Run one render end to end and return the tool's content blocks."""
    paths = workspace.prepare_run(cfg.render_root, run_id)
    workspace.write_scene(paths, code)

    do_render = render_fn or render.render_scene
    outcome = do_render(cfg, paths, scene_class, quality)

    warnings: list[str] = []

    if not outcome.ok or outcome.mp4 is None:
        diagnostic = outcome.diagnostic
        payload = envelope.failure_payload(
            run_id=run_id, diagnostic=diagnostic, code_path=paths.scene
        )
        _record(
            cfg,
            paths=paths,
            tool_name=tool_name,
            scene_name=scene_class,
            title=title,
            quality=quality,
            args_summary=args_summary,
            status="failed",
            assets={},
            warnings=warnings,
        )
        return envelope.content_blocks(payload)

    # The preview is a secondary artifact. ffmpeg may be configured but no longer
    # present (install.ps1 pins absolute paths; the user can move or uninstall it),
    # and every ffmpeg invocation raises FileNotFoundError in that case — so the
    # whole step is guarded, not just the parts we happen to call directly.
    do_preview = preview_fn or postprocess.build_preview
    try:
        preview = do_preview(
            cfg.ffmpeg,
            outcome.mp4,
            paths.out,
            scene_class,
            target_bytes=cfg.gif_target_bytes,
            max_bytes=cfg.gif_max_bytes,
        )
    except Exception as error:  # noqa: BLE001 - a preview fault must not lose the render
        warnings.append(
            f"预览生成失败（动画本身已产出，不影响 MP4 产物）："
            f"{type(error).__name__}: {error}"
        )
        preview = postprocess.Preview(path=None, kind=None, byte_size=0)
    warnings.extend(preview.warnings)

    duration = 0.0
    if cfg.ffmpeg:
        try:
            duration = postprocess.probe_duration(cfg.ffmpeg, outcome.mp4)
        except Exception as error:  # noqa: BLE001 - the probe is cosmetic, the render is not
            warnings.append(
                f"时长探测失败（动画本身已产出，不影响产物）：{type(error).__name__}: {error}"
            )

    poster = paths.out / f"{scene_class}.png"
    assets: dict = {"mp4": str(outcome.mp4)}
    if preview.path is not None:
        assets["preview"] = str(preview.path)
        assets["previewKind"] = preview.kind
    if poster.exists():
        assets["poster"] = str(poster)

    markdown = (
        envelope.preview_markdown(preview.path) if preview.path is not None else None
    )
    if preview.path is not None and markdown is None:
        warnings.append(
            "预览产物路径含有 Markdown 无法安全表示的字符，已省略内嵌预览，"
            "请把 assets 里的路径直接告诉用户。"
        )

    payload = envelope.success_payload(
        run_id=run_id,
        scene_name=scene_class,
        assets=assets,
        preview_markdown=markdown,
        duration_sec=duration,
        render_seconds=outcome.seconds,
        preview_bytes=preview.byte_size,
        quality=quality,
        warnings=warnings,
    )

    extra = _record(
        cfg,
        paths=paths,
        tool_name=tool_name,
        scene_name=scene_class,
        title=title,
        quality=quality,
        args_summary=args_summary,
        status="ok",
        assets=assets,
        warnings=warnings,
    )
    if extra:
        payload["warnings"] = warnings + extra

    return envelope.content_blocks(payload, preview.path, preview.kind)


def _record(
    cfg: config_mod.Config,
    *,
    paths: workspace.RunPaths,
    tool_name: str,
    scene_name: str,
    title: str | None,
    quality: str,
    args_summary: dict,
    status: str,
    assets: dict,
    warnings: list[str],
) -> list[str]:
    """Persist run metadata and the index entry. Never raises."""
    notes: list[str] = []
    preview_url = ""
    if assets.get("preview"):
        markdown = envelope.preview_markdown(assets["preview"])
        if markdown:
            preview_url = markdown.split("](", 1)[1].rstrip(")")

    meta = {
        "runId": paths.run_id,
        "tool": tool_name,
        "sceneName": scene_name,
        "title": title,
        "status": status,
        "quality": quality,
        "createdAt": _iso_now(),
        "assets": assets,
        "previewUrlPath": preview_url,
        "args": args_summary,
        "warnings": list(warnings),
    }

    try:
        workspace.write_meta(paths, meta)
        index.upsert_run(cfg.render_root, meta)
    except Exception as error:  # noqa: BLE001 - a bookkeeping fault must not lose the render
        notes.append(f"索引未更新（渲染结果仍然有效）：{type(error).__name__}: {error}")
        return notes

    try:
        _prune_and_reconcile(cfg, paths.run_id)
    except Exception as error:  # noqa: BLE001 - retention is best effort
        notes.append(f"清理旧 run 失败：{type(error).__name__}: {error}")
    return notes
