"""Stdio entry point.

Adds its own directory to `sys.path` first, so `manim_mcp` imports no matter
which working directory DSH spawns the process from.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from manim_mcp.app import main  # noqa: E402  (import must follow the path fix)

if __name__ == "__main__":
    raise SystemExit(main())
