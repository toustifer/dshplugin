"""Manual smoke: talk to the real server over stdio, exactly as DSH will.

Not collected by pytest (it lives outside `testpaths` and has no test_ prefix).
Run it after changing app.py or server.py:

    python tests/manual/stdio_smoke.py
"""

import asyncio
import json
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

SERVER = r"D:\myprogram\dshplugin\manim-mcp\server.py"
EXPECTED = {
    "equation", "graph", "diagram", "compare",
    "render", "check", "style_guide", "runs",
}


async def main() -> int:
    transport = StdioTransport(command=sys.executable, args=[SERVER])
    async with Client(transport) as client:
        names = {tool.name for tool in await client.list_tools()}
        print("tools:", sorted(names))
        if names != EXPECTED:
            print(f"FAIL: expected {sorted(EXPECTED)}")
            return 1

        result = await client.call_tool("check", {"code": "from manim import *\n"})
        payload = json.loads(result.content[0].text)
        print("check ok:", payload["ok"], "issues:", payload["issues"])
        if payload["ok"] is not False:
            print("FAIL: check should reject code without a Scene subclass")
            return 1

    print("stdio smoke PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
