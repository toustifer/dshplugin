"""Acceptance: drive all four declarative tools through the real stdio server.

`render_templates.py` proves the *templates* compile and render, but it calls
`scenes.build` directly, so it exercises neither the tool layer nor the run
gallery. This script goes through the MCP server over stdio instead, which is the
only path that writes `run.json` and `renders/index.json`.

    D:\\ProgramData\\anaconda3\\python.exe tests\\manual\\acceptance_tools.py

Exits non-zero unless every tool succeeds with a real preview artifact.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "manim-mcp" / "server.py"
INDEX = REPO / "renders" / "index.json"

CASES = [
    ("equation", dict(
        title="欧拉恒等式",
        steps=[
            r"e^{i\theta} = \cos\theta + i\sin\theta",
            r"e^{i\pi} = -1",
            r"e^{i\pi} + 1 = 0",
        ],
        highlight=["", r"-1", r"+ 1"],
    )),
    ("graph", dict(
        title="切线与面积",
        expressions=["x**2"],
        highlight={"x": 1.0, "tangent": True, "area": [0.0, 2.0]},
    )),
    ("diagram", dict(
        title="快速排序的分治",
        nodes=[
            {"id": "in", "label": "待排序数组", "kind": "terminal"},
            {"id": "pivot", "label": "选基准并分区", "kind": "process"},
            {"id": "check", "label": "子数组大小 > 1 ?", "kind": "decision"},
            {"id": "recurse", "label": "递归处理两侧", "kind": "process"},
            {"id": "out", "label": "已排序", "kind": "terminal"},
        ],
        edges=[
            {"from": "in", "to": "pivot"},
            {"from": "pivot", "to": "check"},
            {"from": "check", "to": "recurse", "label": "是"},
            {"from": "check", "to": "out", "label": "否"},
            {"from": "recurse", "to": "check", "label": "回到判定"},
        ],
    )),
    ("compare", dict(
        title="两种开发顺序",
        left={"title": "错误做法", "items": ["先写实现", "再补测试", "改动就返工"]},
        right={"title": "推荐做法", "items": ["先写测试", "再写实现", "改动有保护"]},
    )),
]


async def main() -> int:
    transport = StdioTransport(command=sys.executable, args=[str(SERVER)])
    failures = 0
    seen: list[str] = []
    async with Client(transport) as client:
        for name, arguments in CASES:
            result = await client.call_tool(name, arguments)
            payload = json.loads(result.content[0].text)
            if not payload.get("ok"):
                print(f"[FAIL] {name}: {json.dumps(payload.get('error', payload), ensure_ascii=False)}")
                failures += 1
                continue

            run_id = payload.get("runId")
            assets = payload.get("assets") or {}
            images = sum(1 for block in result.content if getattr(block, "type", "") == "image")
            missing = [
                key for key in ("mp4", "preview", "poster")
                if not Path(str(assets.get(key, ""))).is_file()
            ]
            markdown_ok = str(payload.get("previewMarkdown", "")).startswith("![anim](/D:/")
            preview_bytes = payload.get("previewBytes") or 0
            problems = []
            if images != 1:
                problems.append(f"expected one image block, got {images}")
            if missing:
                problems.append(f"missing artifacts on disk: {missing}")
            if not markdown_ok:
                problems.append(f"bad previewMarkdown {payload.get('previewMarkdown')!r}")
            if preview_bytes <= 0:
                problems.append(f"previewBytes={preview_bytes}")

            if problems:
                print(f"[FAIL] {name}: {'; '.join(problems)}")
                failures += 1
                continue

            seen.append(str(run_id))
            print(
                f"[PASS] {name}: run={run_id} kind={assets.get('previewKind')} "
                f"mp4={Path(assets['mp4']).stat().st_size}B "
                f"gif={Path(assets['preview']).stat().st_size}B "
                f"png={Path(assets['poster']).stat().st_size}B image_blocks={images}"
            )

    if not INDEX.is_file():
        print("\nindex.json: MISSING")
        failures += 1
    else:
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        records = index.get("runs", [])
        indexed = {record.get("runId") for record in records}
        untracked = [run_id for run_id in seen if run_id not in indexed]
        print(f"\nindex.json: version={index.get('version')} runs={len(records)}")
        if untracked:
            print(f"index.json: does not mention {untracked}")
            failures += 1

    total = len(CASES)
    print(f"\n{total - failures} ok, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
