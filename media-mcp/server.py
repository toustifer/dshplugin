"""stdio entry point. Adds its own directory so `media_mcp` imports work from any cwd."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from media_mcp.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
