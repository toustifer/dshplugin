"""FastMCP assembly, plus the tool description that carries all behaviour guidance.

There is deliberately no Skill for this capability. The shipped `read_image` and
`present` tools keep their guidance in their own descriptions, and a Skill has a failure
mode this feature cannot afford: if the router does not load it, the model produces a
video and never hands it over. A description is always in context.
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .tools.publish import publish

TOOL_DESCRIPTION = """\
把一个本地文件发布到对话里，让用户直接看到/听到/读到它（视频会内嵌播放、音频会内嵌播放、
PDF 会显示前 3 页、图片直接显示、其它格式给出文件名与大小）。

**什么时候该发**：你刚产出的东西是用户要「看」的——视频、音频、PDF、图片、报告。
用一段文字描述它，不如让他直接看到。

**什么时候不要发**：中间产物、日志、调试截图；用户没要求看的；一句话就能说清的东西；
同一份文件在同一轮里重复发。

**一轮最多发 3 个**。再多会刷屏，重点反而被淹没。

**上限 20 MiB**。超了就压缩或切片，或者只把路径写在正文里并说明原因——**不要反复重试**。

失败时会返回 `reason`（missing / not-a-file / outside-root / wrong-drive / too-large /
unreferenceable）和 `hint`，按 `hint` 纠正后重试一次；仍失败就把路径写进正文，不要卡住。
"""


def build_server(cfg=None):
    config = cfg or load_config()
    server = FastMCP("media")

    @server.tool(name="publish_file", description=TOOL_DESCRIPTION)
    def publish_file(path: str, title: str | None = None) -> dict:
        """Publish one existing file to the conversation. `path` must be absolute."""
        return publish(path, title, config)

    return server


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in args:
        from .selftest import run

        return run(load_config())
    if "--doctor" in args:
        import json

        print(json.dumps(load_config().doctor(), ensure_ascii=False, indent=2))
        return 0
    build_server().run()
    return 0
