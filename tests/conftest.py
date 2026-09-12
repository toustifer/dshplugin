"""Make the MCP package and the installer importable without installing them."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PARENT = REPO_ROOT / "manim-mcp"
TOOLS_DIR = REPO_ROOT / "tools"

for entry in (PACKAGE_PARENT, TOOLS_DIR, REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
