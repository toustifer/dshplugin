"""FastMCP assembly.

Tool bodies are thin: they adapt MCP arguments into engine calls and never do
bookkeeping of their own, so every path ends in the same envelope and the same
content-block pair.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import sys
from contextlib import AbstractAsyncContextManager
from collections.abc import Callable
from typing import Any, Literal

from fastmcp import FastMCP
from mcp.server.fastmcp.server import Settings
from mcp.types import ImageContent, TextContent

from . import config as config_mod
from . import style as style_mod
from .tools import check as check_tool
from .tools import declarative, envelope
from .tools import render as render_tool
from .tools import runs as runs_tool
from .tools import style_guide as style_guide_tool

LOG = logging.getLogger("manim-mcp")

# fastmcp 3.4.0 leaves the generic lifespan annotation unresolved under
# pydantic-settings 2.15; rebuild it before Settings is instantiated.
Settings.model_rebuild(
    _types_namespace={
        "FastMCP": FastMCP,
        "LifespanResultT": Any,
        "Callable": Callable,
        "AbstractAsyncContextManager": AbstractAsyncContextManager,
    }
)

Quality = Literal["draft", "final"]

INSTRUCTIONS = (
    "把解释性动画渲染成视频。优先用 equation / graph / diagram / compare 四个模板："
    "它们只需要声明式参数，比手写 Manim 代码快得多也稳得多。"
    "只有四个模板都表达不了时才用 render 写原始代码；写代码前先用 check 花 0.1 秒体检，"
    "不要用一次 10 秒的渲染去发现一个语法错误。"
)


def replace(cfg: config_mod.Config, **changes) -> config_mod.Config:
    """A copy with the given fields replaced (used by tests and the self-test)."""
    return dataclasses.replace(cfg, **changes)


class Renderer:
    """Serialises renders and keeps blocking work off the event loop."""

    def __init__(self, cfg: config_mod.Config) -> None:
        self._cfg = cfg
        self._gate = asyncio.Semaphore(cfg.max_concurrency)

    async def run(self, work, *args, **kwargs):
        async with self._gate:
            return await asyncio.to_thread(work, self._cfg, *args, **kwargs)


def build_server(cfg: config_mod.Config) -> FastMCP:
    mcp = FastMCP("manim", instructions=INSTRUCTIONS)
    renderer = Renderer(cfg)

    @mcp.tool(
        name="equation",
        description=(
            "把一串 LaTeX 公式逐步变形，展示推导过程（3b1b 式）。"
            "steps 是 2-6 个 LaTeX 字符串，每一步一个状态。"
        ),
    )
    async def equation(
        steps: list[str],
        title: str | None = None,
        highlight: list[str] | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "equation",
            quality=quality,
            title=title,
            params={"steps": steps, "title": title, "highlight": highlight},
        )

    @mcp.tool(
        name="graph",
        description=(
            "函数图像，可叠加切线、面积填充与参数滑动。"
            "expressions 是 1-3 个 Python 表达式字符串，变量是 x，可用 np.*。"
        ),
    )
    async def graph(
        expressions: list[str],
        title: str | None = None,
        x_range: list[float] | None = None,
        y_range: list[float] | None = None,
        highlight: dict | None = None,
        parameter: dict | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "graph",
            quality=quality,
            title=title,
            params={
                "expressions": expressions,
                "title": title,
                "x_range": x_range,
                "y_range": y_range,
                "highlight": highlight,
                "parameter": parameter,
            },
        )

    @mcp.tool(
        name="diagram",
        description=(
            "流程 / 架构 / 因果关系的框图。nodes 是 [{id, label, kind}]，"
            "edges 是 [{from, to, label?}]；kind 取 process/decision/terminal/data。"
        ),
    )
    async def diagram(
        nodes: list[dict],
        edges: list[dict],
        title: str | None = None,
        layout: Literal["vertical", "horizontal"] = "vertical",
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "diagram",
            quality=quality,
            title=title,
            params={"nodes": nodes, "edges": edges, "title": title, "layout": layout},
        )

    @mcp.tool(
        name="compare",
        description=(
            "左右对照，突出两种做法或两个概念的差异。"
            "left/right 各是 {title, items}，items 为 1-5 条。"
        ),
    )
    async def compare(
        left: dict,
        right: dict,
        title: str | None = None,
        left_color: str | None = None,
        right_color: str | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "compare",
            quality=quality,
            title=title,
            params={
                "left": left,
                "right": right,
                "title": title,
                "left_color": left_color,
                "right_color": right_color,
            },
        )

    @mcp.tool(
        name="render",
        description=(
            "逃生口：渲染任意 Manim 代码。code 必须是完整文件，含 `from manim import *` "
            "与至少一个 Scene 子类。调用前先用 check 体检。"
        ),
    )
    async def render(
        code: str,
        scene_name: str | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            render_tool.run_code,
            code=code,
            scene_name=scene_name,
            quality=quality,
        )

    @mcp.tool(
        name="check",
        description=(
            "0.1 秒静态体检：语法、是否 import manim、是否有带 construct 的 Scene 子类。"
            "不渲染。写原始代码后应先调用它。"
        ),
    )
    async def check(code: str) -> list[TextContent | ImageContent]:
        return envelope.content_blocks(check_tool.check_code(code))

    @mcp.tool(
        name="style_guide",
        description=(
            "取本机的精确风格常量：调色板 hex、可用的中文字体名、Manim API 注意事项、"
            "4 个模板的参数说明、以及一段可直接改用的代码骨架。写代码前调用。"
        ),
    )
    async def style_guide() -> list[TextContent | ImageContent]:
        return envelope.content_blocks(
            style_guide_tool.style_guide_payload(style_mod.detect_cjk_font())
        )

    @mcp.tool(
        name="runs",
        description=(
            "查看历史渲染。action=list 列出最近的 run；action=get 配 runId 取回那次生成的"
            "完整 scene.py 源码，用于「把刚才那个动画改一下」。"
        ),
    )
    async def runs(
        action: Literal["list", "get"],
        run_id: str | None = None,
        limit: int = 20,
    ) -> list[TextContent | ImageContent]:
        return envelope.content_blocks(
            runs_tool.dispatch(cfg.render_root, action, run_id, limit)
        )

    return mcp


def selftest(cfg: config_mod.Config) -> int:
    """One real render, used by install.ps1 to prove the whole chain works."""
    from .tools import selftest as selftest_tool

    return selftest_tool.run(cfg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manim-mcp", description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="渲染一个样例场景后退出")
    args = parser.parse_args(argv)

    try:
        cfg = config_mod.load_config()
    except config_mod.ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        stream=sys.stderr,  # stdout carries the MCP frames and must stay clean
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    LOG.debug("resolved config: %s", cfg)

    if args.selftest:
        return selftest(cfg)

    build_server(cfg).run(transport="stdio", show_banner=False)
    return 0
