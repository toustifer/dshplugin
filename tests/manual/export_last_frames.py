"""Export the last frame of each run produced by acceptance_tools.py."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INDEX = REPO / "renders" / "index.json"
OUT = REPO / "renders" / "_lastframes"
FFMPEG = r"D:\tools\system_cmd\ffmpeg.EXE"
TOOLS = ["equation", "graph", "diagram", "compare"]


def main() -> int:
    records = json.loads(INDEX.read_text(encoding="utf-8"))["runs"]
    OUT.mkdir(parents=True, exist_ok=True)
    for tool in TOOLS:
        record = next((r for r in records if r.get("tool") == tool), None)
        if record is None:
            print(f"{tool}: no record in index.json")
            continue
        mp4 = Path(record["assets"]["mp4"])
        png = OUT / f"{tool}.png"
        result = subprocess.run(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
             "-sseof", "-0.2", "-i", str(mp4), "-frames:v", "1", "-update", "1", str(png)],
            check=False,
        )
        print(f"{tool}: run={record['runId']} rc={result.returncode} "
              f"png={png} bytes={png.stat().st_size if png.exists() else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
