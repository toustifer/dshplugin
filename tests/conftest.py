"""Make the MCP package importable without installing it."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PARENT = REPO_ROOT / "manim-mcp"

for entry in (PACKAGE_PARENT, REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
