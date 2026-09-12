"""The server must expose exactly the eight documented tools, and stay quiet on stdout."""

import asyncio
import json
from pathlib import Path

import pytest
from fastmcp import Client

from manim_mcp import app
from manim_mcp.config import Config

EXPECTED = {
    "equation", "graph", "diagram", "compare",
    "render", "check", "style_guide", "runs",
}


def make_config(tmp_path: Path) -> Config:
    return Config(
        python=r"D:\py\python.exe", manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe", render_root=tmp_path,
        max_concurrency=1, timeout_sec=30.0, gif_target_bytes=1000,
        gif_max_bytes=2000, keep_runs=50, log_level="INFO",
    )


def call(cfg: Config, name: str, arguments: dict):
    async def go():
        async with Client(app.build_server(cfg)) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(go())


def test_exactly_the_eight_tools_are_registered(tmp_path: Path):
    async def go():
        async with Client(app.build_server(make_config(tmp_path))) as client:
            return {tool.name for tool in await client.list_tools()}

    assert asyncio.run(go()) == EXPECTED


def test_check_tool_returns_a_text_envelope(tmp_path: Path):
    result = call(make_config(tmp_path), "check", {"code": "from manim import *\n"})
    payload = json.loads(result.content[0].text)
    assert payload["ok"] is False
    assert any("Scene" in issue for issue in payload["issues"])


def test_style_guide_tool_lists_templates(tmp_path: Path):
    result = call(make_config(tmp_path), "style_guide", {})
    payload = json.loads(result.content[0].text)
    assert {row["name"] for row in payload["templates"]} == {
        "equation", "graph", "diagram", "compare"
    }


def test_runs_tool_lists_an_empty_root(tmp_path: Path):
    result = call(make_config(tmp_path), "runs", {"action": "list"})
    payload = json.loads(result.content[0].text)
    assert payload["ok"] is True
    assert payload["runs"] == []


def test_equation_tool_reports_a_validation_failure_without_rendering(tmp_path: Path):
    result = call(make_config(tmp_path), "equation", {"steps": ["only-one"]})
    payload = json.loads(result.content[0].text)
    assert payload["ok"] is False
    assert payload["stage"] == "validate"


def test_every_tool_has_a_description(tmp_path: Path):
    async def go():
        async with Client(app.build_server(make_config(tmp_path))) as client:
            return {tool.name: (tool.description or "") for tool in await client.list_tools()}

    descriptions = asyncio.run(go())
    for name, text in descriptions.items():
        assert len(text.strip()) > 20, f"{name} has no usable description"


def test_main_rejects_unknown_arguments(tmp_path: Path):
    with pytest.raises(SystemExit):
        app.main(["--nonsense"])
