"""Render one scene per template with real Manim.

Unit tests can only assert on the generated *source text*, and a great deal gets
through that net: `json.dumps(None)` emits `null`, which Python's parser accepts
as an identifier and only rejects with `NameError` when Manim imports the file.
Only an actual render catches that class of defect, so this script is the
acceptance gate for the templates.

Not collected by pytest (outside `testpaths`, no `test_` prefix). Run:

    D:\\ProgramData\\anaconda3\\python.exe tests\\manual\\render_templates.py

Exits non-zero if any template fails to render.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "manim-mcp"))

from manim_mcp import scenes  # noqa: E402
from manim_mcp import style as style_mod  # noqa: E402

PYTHON = sys.executable
OUT = REPO / "renders" / "_template-verify"

CASES = {
    "equation": dict(
        title="欧拉恒等式",
        steps=[
            r"e^{i\theta} = \cos\theta + i\sin\theta",
            r"e^{i\pi} = -1",
            r"e^{i\pi} + 1 = 0",
        ],
        highlight=["", r"-1", r"+ 1"],
    ),
    "graph": dict(
        title="切线与面积",
        expressions=["x**2"],
        highlight={"x": 1.0, "tangent": True, "area": [0.0, 2.0]},
    ),
    "diagram": dict(
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
    ),
    "compare": dict(
        title="两种开发顺序",
        left={"title": "错误做法", "items": ["先写实现", "再补测试", "改动就返工"]},
        right={"title": "推荐做法", "items": ["先写测试", "再写实现", "改动有保护"]},
    ),
}

# A parameter-driven graph is the riskiest path (always_redraw over an eval'd
# expression), so it gets a case of its own beyond the four representative ones.
EXTRA = {
    "graph_parameter": (
        "graph",
        dict(
            title="参数滑动",
            expressions=["a * np.sin(x)"],
            parameter={"symbol": "a", "from": 0.5, "to": 3.0},
        ),
    )
}


def render(label: str, template: str, params: dict, timeout: int = 300) -> tuple[bool, str]:
    scene_class, code = scenes.build(template, cjk_font=style_mod.detect_cjk_font(), **params)
    work = OUT / label
    work.mkdir(parents=True, exist_ok=True)
    scene_file = work / "scene.py"
    scene_file.write_text(code, encoding="utf-8")

    result = subprocess.run(
        [
            PYTHON, "-m", "manim", "render", "-ql", "--format=mp4",
            "--media_dir", str(work / "media"),
            "--output_file", scene_class,
            str(scene_file), scene_class,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    produced = list((work / "media").glob(f"videos/**/{scene_class}.mp4"))
    if result.returncode == 0 and produced:
        return True, f"{produced[0].stat().st_size} bytes -> {produced[0].name}"
    return False, (result.stderr or "")[-600:]


def main() -> int:
    font = style_mod.detect_cjk_font()
    print(f"cjk font: {font}")
    failures = 0
    cases = [(name, name, params) for name, params in CASES.items()]
    cases += [(label, template, params) for label, (template, params) in EXTRA.items()]
    for label, template, params in cases:
        ok, detail = render(label, template, params)
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: {detail}")
        failures += 0 if ok else 1
    print(f"\n{len(cases) - failures} ok, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
