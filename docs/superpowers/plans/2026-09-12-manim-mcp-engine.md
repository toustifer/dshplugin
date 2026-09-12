# manim-mcp（组件 1）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 stdio MCP 服务，向模型暴露 8 个工具，把「公式推导 / 函数图像 / 流程结构 / 左右对照 / 任意 Manim 代码」渲染成 MP4，并自动产出 GIF/WebP/PNG 预览与结构化诊断。

**Architecture:** 三层。`config` 负责环境探测与配置；`engine` 是无 UI 的纯逻辑层（run 目录、索引、诊断、后处理、子进程渲染）；`scenes` 是把声明式参数编译成 Manim 源码的模板层；`tools` 是 MCP 工具层，统一走 `pipeline` 编排并把结果装进「文本信封 + 图片内容块」。所有 engine/scenes/config 逻辑都是同步纯函数或对子进程的薄封装，因此可用 pytest 完全覆盖，不需要真机渲染。

**Tech Stack:** Python 3.13、FastMCP 3.4.0（`mcp.types.TextContent/ImageContent`）、Manim Community 0.20.1、FFmpeg、MiKTeX、pytest 8.3.0。

**Spec:** `docs/superpowers/specs/2026-09-12-manim-visual-explainer-design.md`

**对 Spec 的两处偏离（已在计划内落实，需回写 Spec）：**

1. `manim-mcp/` 下增加 `manim_mcp/` 包嵌套与 `server.py` 启动器，使 pytest 可以直接 `import manim_mcp.*`（Spec §5 已同步）。
2. `tools/` 下增加 `pipeline.py`（编排逻辑），避免 `__init__.py` 承担过多职责。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `pytest.ini` | pytest 配置（testpaths、严格标记） |
| `tests/conftest.py` | 把 `manim-mcp/` 加入 `sys.path`；提供 fixture |
| `manim-mcp/server.py` | stdio 启动器：把自身目录加入 `sys.path` 后调用 `manim_mcp.app.main()` |
| `manim-mcp/manim_mcp/__init__.py` | 版本常量 |
| `manim-mcp/manim_mcp/config.py` | 配置解析、工具探测、`manim_argv()` |
| `manim-mcp/manim_mcp/style.py` | 视觉常量、中文字体探测、`preamble()` |
| `manim-mcp/manim_mcp/engine/workspace.py` | run 目录命名/布局/元数据/保留清理 |
| `manim-mcp/manim_mcp/engine/index.py` | `renders/index.json` 原子读写与对账 |
| `manim-mcp/manim_mcp/engine/diagnostics.py` | stderr → 结构化诊断 + 修复提示 |
| `manim-mcp/manim_mcp/engine/postprocess.py` | MP4 → GIF/WebP/PNG 与体积降级链 |
| `manim-mcp/manim_mcp/engine/render.py` | manim 子进程调用、超时杀进程树、产物定位 |
| `manim-mcp/manim_mcp/scenes/__init__.py` | 模板注册表与 `build()` |
| `manim-mcp/manim_mcp/scenes/{equation,graph,diagram,compare}.py` | 4 个模板的源码生成器 |
| `manim-mcp/manim_mcp/tools/envelope.py` | 统一信封 + 双内容块组装 |
| `manim-mcp/manim_mcp/tools/pipeline.py` | 渲染编排（唯一的副作用全流程） |
| `manim-mcp/manim_mcp/tools/declarative.py` | `equation`/`graph`/`diagram`/`compare` 工具体 |
| `manim-mcp/manim_mcp/tools/render.py` | `render` 逃生口工具体 |
| `manim-mcp/manim_mcp/tools/check.py` | `check` 秒级体检 |
| `manim-mcp/manim_mcp/tools/style_guide.py` | `style_guide` 常量与代码范式 |
| `manim-mcp/manim_mcp/tools/runs.py` | `runs` 历史查询 |
| `manim-mcp/manim_mcp/app.py` | FastMCP 组装、`main()`、`--selftest` |

---

## Task 1: 包骨架与 pytest 基线

**Files:**
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `manim-mcp/server.py`
- Create: `manim-mcp/manim_mcp/__init__.py`
- Create: `manim-mcp/manim_mcp/engine/__init__.py`
- Create: `manim-mcp/manim_mcp/scenes/__init__.py`（本任务先建空文件，Task 9 填内容）
- Create: `manim-mcp/manim_mcp/tools/__init__.py`
- Test: `tests/test_package.py`

- [ ] **Step 1: 写失败测试**

`tests/test_package.py`:

```python
"""The package must import from a bare checkout, with no install step."""

import manim_mcp
from manim_mcp import config  # noqa: F401  (import proves the package path works)


def test_version_is_declared():
    assert isinstance(manim_mcp.__version__, str)
    assert manim_mcp.__version__.strip() != ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_package.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp'`

- [ ] **Step 3: 写最小实现**

`pytest.ini`:

```ini
[pytest]
testpaths = tests
addopts = -q
```

`tests/__init__.py`:

```python
"""Test package.

Making `tests` a package is what lets one test module import the shared render
and preview stubs from `tests.helpers` instead of duplicating them.
"""
```

`tests/conftest.py`:

```python
"""Make the MCP package importable without installing it."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PARENT = REPO_ROOT / "manim-mcp"

for entry in (PACKAGE_PARENT, REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
```

`manim-mcp/manim_mcp/__init__.py`:

```python
"""Manim MCP server: turn an LLM's intent into a rendered animation."""

__version__ = "0.1.0"
```

`manim-mcp/manim_mcp/engine/__init__.py`:

```python
"""Pure logic: run workspaces, index, diagnostics, postprocess, rendering."""
```

`manim-mcp/manim_mcp/scenes/__init__.py`:

```python
"""Declarative scene templates."""
```

`manim-mcp/manim_mcp/tools/__init__.py`:

```python
"""MCP tool bodies."""
```

`manim-mcp/server.py`:

```python
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
```

> `server.py` 引用的 `manim_mcp.app` 在 Task 18 才创建。本任务的测试只断言包可导入，因此不会触发该 import。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_package.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
git add pytest.ini tests/conftest.py tests/__init__.py tests/test_package.py manim-mcp
git commit -m "feat(manim-mcp): 包骨架与 pytest 基线"
```

---

## Task 2: `config.py` — 配置解析与工具探测

**Files:**
- Create: `manim-mcp/manim_mcp/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

`tests/test_config.py`:

```python
"""Configuration parsing must be total: bad input raises, absent input defaults."""

import sys
from pathlib import Path

import pytest

from manim_mcp import config as config_mod
from manim_mcp.config import ConfigError, load_config


def test_defaults_when_env_is_empty():
    cfg = load_config(env={})
    assert cfg.python == sys.executable
    assert cfg.render_root == config_mod.DEFAULT_RENDER_ROOT
    assert cfg.max_concurrency == 1
    assert cfg.timeout_sec == 180.0
    assert cfg.gif_target_bytes == 8 * 1024 * 1024
    assert cfg.gif_max_bytes == 18 * 1024 * 1024
    assert cfg.keep_runs == 50
    assert cfg.log_level == "INFO"


def test_env_overrides_are_read():
    cfg = load_config(env={
        "MANIM_MCP_PYTHON": r"D:\py\python.exe",
        "MANIM_MCP_MANIM": r"D:\py\Scripts\manim.exe",
        "MANIM_MCP_FFMPEG": r"D:\tools\ffmpeg.exe",
        "MANIM_MCP_RENDER_ROOT": r"D:\out",
        "MANIM_MCP_MAX_CONCURRENCY": "3",
        "MANIM_MCP_TIMEOUT_SEC": "45.5",
        "MANIM_MCP_KEEP_RUNS": "0",
        "MANIM_MCP_LOG_LEVEL": "DEBUG",
    })
    assert cfg.python == r"D:\py\python.exe"
    assert cfg.manim == r"D:\py\Scripts\manim.exe"
    assert cfg.ffmpeg == r"D:\tools\ffmpeg.exe"
    assert cfg.render_root == Path(r"D:\out")
    assert cfg.max_concurrency == 3
    assert cfg.timeout_sec == 45.5
    assert cfg.keep_runs == 0
    assert cfg.log_level == "debug"


def test_non_integer_number_is_rejected():
    with pytest.raises(ConfigError) as caught:
        load_config(env={"MANIM_MCP_MAX_CONCURRENCY": "many"})
    assert "MANIM_MCP_MAX_CONCURRENCY" in str(caught.value)


def test_negative_concurrency_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_MAX_CONCURRENCY": "-1"})


def test_zero_concurrency_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_MAX_CONCURRENCY": "0"})


def test_zero_keep_runs_is_allowed():
    assert load_config(env={"MANIM_MCP_KEEP_RUNS": "0"}).keep_runs == 0


def test_target_must_not_exceed_hard_cap():
    with pytest.raises(ConfigError) as caught:
        load_config(env={
            "MANIM_MCP_GIF_TARGET_BYTES": "20000000",
            "MANIM_MCP_GIF_MAX_BYTES": "10000000",
        })
    assert "GIF_TARGET_BYTES" in str(caught.value)


def test_manim_argv_prefers_the_explicit_binary():
    cfg = load_config(env={"MANIM_MCP_MANIM": r"D:\py\Scripts\manim.exe"})
    assert config_mod.manim_argv(cfg, "render") == [r"D:\py\Scripts\manim.exe", "render"]


def test_manim_argv_falls_back_to_module_invocation():
    cfg = config_mod.Config(
        python=r"D:\py\python.exe", manim=None, ffmpeg=None,
        render_root=Path("."), max_concurrency=1, timeout_sec=1.0,
        gif_target_bytes=1, gif_max_bytes=2, keep_runs=0, log_level="info",
    )
    assert config_mod.manim_argv(cfg, "render") == [
        r"D:\py\python.exe", "-m", "manim", "render",
    ]


def test_log_level_is_normalised_to_upper_case():
    assert load_config(env={"MANIM_MCP_LOG_LEVEL": "debug"}).log_level == "DEBUG"


def test_invalid_log_level_is_rejected():
    with pytest.raises(ConfigError):
        load_config(env={"MANIM_MCP_LOG_LEVEL": "chatty"})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.config'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/config.py`:

```python
"""Configuration and tool discovery.

Every value can be pinned through an environment variable, because the DSH MCP
row hands the child a *scrubbed* environment: anything not passed explicitly may
be absent, including a useful PATH. When nothing is pinned we probe, and when the
probe fails we fall back to a value that still works on this machine.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# <repo>/manim-mcp/manim_mcp/config.py -> parents[2] is <repo>
DEFAULT_RENDER_ROOT = Path(__file__).resolve().parents[2] / "renders"

DEFAULT_TIMEOUT_SEC = 180.0
DEFAULT_GIF_TARGET_BYTES = 8 * 1024 * 1024
DEFAULT_GIF_MAX_BYTES = 18 * 1024 * 1024
DEFAULT_KEEP_RUNS = 50

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

ENV_PREFIX = "MANIM_MCP_"


class ConfigError(ValueError):
    """A environment value is present but unusable."""


@dataclass(frozen=True)
class Config:
    """Resolved run-time settings."""

    python: str
    manim: str | None
    ffmpeg: str | None
    render_root: Path
    max_concurrency: int
    timeout_sec: float
    gif_target_bytes: int
    gif_max_bytes: int
    keep_runs: int
    log_level: str


def _raw(env: Mapping[str, str], name: str) -> str:
    return str(env.get(f"{ENV_PREFIX}{name}", "") or "").strip()


def _read_str(env: Mapping[str, str], name: str, default: str) -> str:
    value = _raw(env, name)
    return value if value else default


def _read_path(env: Mapping[str, str], name: str, default: Path) -> Path:
    value = _raw(env, name)
    return Path(value) if value else default


def _read_int(
    env: Mapping[str, str], name: str, default: int, *, minimum: int = 0
) -> int:
    value = _raw(env, name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigError(f"{ENV_PREFIX}{name} must be an integer, got {value!r}") from error
    if parsed < minimum:
        raise ConfigError(
            f"{ENV_PREFIX}{name} must be >= {minimum}, got {parsed}"
        )
    return parsed


def _read_float(
    env: Mapping[str, str], name: str, default: float, *, minimum: float = 1.0
) -> float:
    value = _raw(env, name)
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigError(f"{ENV_PREFIX}{name} must be a number, got {value!r}") from error
    if parsed < minimum:
        raise ConfigError(f"{ENV_PREFIX}{name} must be >= {minimum:g}, got {parsed:g}")
    return parsed


def _read_log_level(env: Mapping[str, str]) -> str:
    value = _read_str(env, "LOG_LEVEL", "INFO").upper()
    if value not in LOG_LEVELS:
        raise ConfigError(
            f"{ENV_PREFIX}LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}, got {value!r}"
        )
    return value


def resolve_manim(env: Mapping[str, str]) -> str | None:
    """Prefer an explicit binary; otherwise whatever `manim` is on PATH."""
    explicit = _raw(env, "MANIM")
    if explicit:
        return explicit
    return shutil.which("manim")


def resolve_ffmpeg(env: Mapping[str, str]) -> str | None:
    explicit = _raw(env, "FFMPEG")
    if explicit:
        return explicit
    return shutil.which("ffmpeg")


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Build a validated Config. Raises ConfigError on an unusable value."""
    source: Mapping[str, str] = sys.environ if env is None else env  # type: ignore[attr-defined]
    if env is None:  # pragma: no cover - exercised only in production
        import os

        source = os.environ

    target = _read_int(source, "GIF_TARGET_BYTES", DEFAULT_GIF_TARGET_BYTES, minimum=1)
    hard_max = _read_int(source, "GIF_MAX_BYTES", DEFAULT_GIF_MAX_BYTES, minimum=1)
    if target > hard_max:
        raise ConfigError(
            f"{ENV_PREFIX}GIF_TARGET_BYTES ({target}) must not exceed "
            f"{ENV_PREFIX}GIF_MAX_BYTES ({hard_max})"
        )

    return Config(
        python=_read_str(source, "PYTHON", sys.executable),
        manim=resolve_manim(source),
        ffmpeg=resolve_ffmpeg(source),
        render_root=_read_path(source, "RENDER_ROOT", DEFAULT_RENDER_ROOT),
        max_concurrency=_read_int(source, "MAX_CONCURRENCY", 1, minimum=1),
        timeout_sec=_read_float(source, "TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC, minimum=1.0),
        gif_target_bytes=target,
        gif_max_bytes=hard_max,
        keep_runs=_read_int(source, "KEEP_RUNS", DEFAULT_KEEP_RUNS, minimum=0),
        log_level=_read_log_level(source),
    )


def manim_argv(cfg: Config, *args: str) -> list[str]:
    """Command prefix that runs Manim.

    The `-m manim` form uses the same interpreter that runs this server, so Manim
    is guaranteed importable; it prints one harmless RuntimeWarning that the
    diagnostics layer strips.
    """
    if cfg.manim:
        return [cfg.manim, *args]
    return [cfg.python, "-m", "manim", *args]


def python_argv(cfg: Config, *args: str) -> list[str]:
    """Command prefix that runs Python (used for the self-test scene)."""
    return [cfg.python, *args]


def doctor(cfg: Config) -> list[tuple[str, bool, str]]:
    """Dependency rows for `--selftest` and install-time reporting."""
    rows: list[tuple[str, bool, str]] = [
        ("python", bool(cfg.python), cfg.python),
        (
            "manim",
            cfg.manim is not None or True,
            cfg.manim or f"{cfg.python} -m manim",
        ),
        ("ffmpeg", cfg.ffmpeg is not None, cfg.ffmpeg or "not found on PATH"),
        (
            "latex",
            shutil.which("latex") is not None,
            shutil.which("latex") or "not found on PATH",
        ),
        ("render_root", True, str(cfg.render_root)),
    ]
    return rows
```

> 注意 `load_config` 里那段 `sys.environ` 是笔误遗留的坏代码。正确写法是：

```python
def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Build a validated Config. Raises ConfigError on an unusable value."""
    import os

    source: Mapping[str, str] = os.environ if env is None else env
    ...
```

（Step 3 请直接采用上面的正确版本；`sys.environ` 不存在，写了会让 `env=None` 的调用路径崩。）

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS（10 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/config.py tests/test_config.py
git commit -m "feat(manim-mcp): 配置解析与工具探测"
```

---

## Task 3: `style.py` — 视觉常量与中文字体

**Files:**
- Create: `manim-mcp/manim_mcp/style.py`
- Test: `tests/test_style.py`

- [ ] **Step 1: 写失败测试**

`tests/test_style.py`:

```python
"""Style constants and the CJK font picker, without importing Manim."""

from manim_mcp import style


def test_palette_matches_the_spec():
    assert style.BACKGROUND == "#0E1116"
    assert style.BLUE == "#58C4DD"
    assert style.HIGHLIGHT == "#FFD166"
    assert style.GREEN == "#7BE495"
    assert style.RED == "#FF6B6B"
    assert style.GREY == "#5A6472"


def test_detects_the_first_available_candidate():
    fonts = ["Arial", "SimHei", "Microsoft YaHei"]
    assert style.detect_cjk_font(fonts) == "Microsoft YaHei"


def test_falls_back_to_the_second_candidate():
    assert style.detect_cjk_font(["Arial", "SimHei"]) == "SimHei"


def test_matching_is_case_insensitive():
    assert style.detect_cjk_font(["MICROSOFT YAHEI"]) == "MICROSOFT YAHEI"


def test_returns_none_when_no_cjk_font_exists():
    assert style.detect_cjk_font(["Arial", "Times New Roman"]) is None


def test_loose_match_catches_families_not_in_the_candidate_list():
    assert style.detect_cjk_font(["Arial", "MSYH Custom"]) is None
    assert style.detect_cjk_font(["Arial", "Source Han Serif SC"]) == "Source Han Serif SC"


def test_preamble_declares_every_constant_and_the_helper():
    text = style.preamble("SimHei")
    assert 'config.background_color = "#0E1116"' in text
    assert 'C_BLUE = "#58C4DD"' in text
    assert 'C_HIGHLIGHT = "#FFD166"' in text
    assert 'FONT_CJK = "SimHei"' in text
    assert "def cn(" in text


def test_preamble_without_a_cjk_font_still_compiles():
    text = style.preamble(None)
    assert "FONT_CJK = None" in text
    compile(text, "<preamble>", "exec")


def test_preamble_with_a_font_compiles():
    compile(style.preamble("SimHei"), "<preamble>", "exec")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_style.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.style'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/style.py`:

```python
"""One palette and one CJK font decision, shared by every generated scene.

Templates never hard-code a colour or a font name: they call `preamble()` and use
the constants it emits, so the look stays consistent and a font that is missing on
this machine degrades to a warning instead of a scene full of tofu boxes.
"""

from __future__ import annotations

import json
from typing import Iterable

BACKGROUND = "#0E1116"
BLUE = "#58C4DD"
HIGHLIGHT = "#FFD166"
GREEN = "#7BE495"
RED = "#FF6B6B"
GREY = "#5A6472"

TITLE_SIZE = 44
BODY_SIZE = 32
NOTE_SIZE = 24
PLAY_RUN_TIME = 1.0
TAIL_WAIT = 0.5

# Ordered by preference. Manim's Text() takes a family name resolved by Pango, so
# a family that is not installed renders as boxes rather than raising — hence the
# detection step instead of trusting a default.
CJK_FONT_CANDIDATES = (
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "SimSun",
)

LOOSE_CJK_MARKERS = ("YaHei", "SimHei", "SimSun", "Noto Sans CJK", "Source Han")

PALETTE = {
    "background": BACKGROUND,
    "blue": BLUE,
    "highlight": HIGHLIGHT,
    "green": GREEN,
    "red": RED,
    "grey": GREY,
}


def list_fonts() -> list[str]:
    """Every font family Pango can see. Empty when Manim is not importable."""
    try:
        import manimpango
    except ImportError:
        return []
    try:
        return [str(name) for name in manimpango.list_fonts()]
    except Exception:  # pragma: no cover - a broken font cache must not kill the server
        return []


def detect_cjk_font(fonts: Iterable[str] | None = None) -> str | None:
    """Pick a CJK-capable family, preferring the documented order."""
    available = list(fonts) if fonts is not None else list_fonts()
    by_case = {name.casefold(): name for name in available}

    for candidate in CJK_FONT_CANDIDATES:
        hit = by_case.get(candidate.casefold())
        if hit is not None:
            return hit

    for name in available:
        if any(marker.casefold() in name.casefold() for marker in LOOSE_CJK_MARKERS):
            return name

    return None


def _literal(value: str | None) -> str:
    if value is None:
        return "None"
    return json.dumps(value, ensure_ascii=False)


def preamble(cjk_font: str | None) -> str:
    """Header source that every generated scene starts with.

    Emits the palette, the sizes, the pacing constants, and `cn()` — the only
    text helper templates are allowed to use for prose, so Chinese never falls
    back to a Latin-only family.
    """
    return f'''config.background_color = {_literal(BACKGROUND)}
C_BLUE = {_literal(BLUE)}
C_HIGHLIGHT = {_literal(HIGHLIGHT)}
C_GREEN = {_literal(GREEN)}
C_RED = {_literal(RED)}
C_GREY = {_literal(GREY)}

TITLE_SIZE = {TITLE_SIZE}
BODY_SIZE = {BODY_SIZE}
NOTE_SIZE = {NOTE_SIZE}
PLAY_RUN_TIME = {PLAY_RUN_TIME}
TAIL_WAIT = {TAIL_WAIT}

FONT_CJK = {_literal(cjk_font)}


def cn(text, size=BODY_SIZE, color=WHITE, weight=NORMAL):
    """Text with a CJK-capable family when one exists on this machine."""
    if FONT_CJK is None:
        return Text(text, font_size=size, color=color, weight=weight)
    return Text(text, font=FONT_CJK, font_size=size, color=color, weight=weight)
'''


def style_guide_facts(cjk_font: str | None, fonts: Iterable[str] | None = None) -> dict:
    """The machine-precise half of `style_guide`; the narrative lives in SKILL.md."""
    available = list(fonts) if fonts is not None else list_fonts()
    return {
        "palette": dict(PALETTE),
        "typography": {
            "title": TITLE_SIZE,
            "body": BODY_SIZE,
            "note": NOTE_SIZE,
        },
        "pacing": {"play_run_time": PLAY_RUN_TIME, "tail_wait": TAIL_WAIT},
        "cjkFont": cjk_font,
        "availableCjkFonts": [name for name in available if detect_cjk_font([name]) == name],
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_style.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/style.py tests/test_style.py
git commit -m "feat(manim-mcp): 视觉常量与中文字体探测"
```

---

## Task 4: `engine/workspace.py` — run 目录生命周期

**Files:**
- Create: `manim-mcp/manim_mcp/engine/workspace.py`
- Test: `tests/test_workspace.py`

- [ ] **Step 1: 写失败测试**

`tests/test_workspace.py`:

```python
"""Run directories: safe names, stable layout, honest retention."""

from datetime import datetime
from pathlib import Path

import pytest

from manim_mcp.engine import workspace


def test_run_id_is_ascii_and_filesystem_safe():
    run_id = workspace.new_run_id(datetime(2026, 9, 12, 15, 30, 12), token="a1b2")
    assert run_id == "20260912-153012-a1b2"
    assert workspace.is_valid_run_id(run_id)


def test_generated_run_ids_are_valid_and_unique():
    ids = {workspace.new_run_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(workspace.is_valid_run_id(value) for value in ids)


def test_underscore_and_space_are_rejected():
    assert not workspace.is_valid_run_id("20260912-153012_a1b2")
    assert not workspace.is_valid_run_id("20260912 153012-a1b2")


def test_missing_suffix_is_rejected():
    assert not workspace.is_valid_run_id("20260912-153012")


def test_prepare_run_creates_the_expected_tree(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    assert paths.root == tmp_path / "20260912-153012-a1b2"
    assert paths.media.is_dir()
    assert paths.out.is_dir()
    assert paths.scene == paths.root / "scene.py"
    assert paths.meta == paths.root / "run.json"


def test_prepare_run_is_idempotent(tmp_path: Path):
    first = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    workspace.write_scene(first, "print('hi')\n")
    second = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    assert workspace.read_scene(second) == "print('hi')\n"


def test_prepare_run_rejects_an_unsafe_id(tmp_path: Path):
    with pytest.raises(workspace.WorkspaceError):
        workspace.prepare_run(tmp_path, "../escape")


def test_scene_round_trips_unicode(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    workspace.write_scene(paths, "# 中文注释\nx = 1\n")
    assert "中文注释" in workspace.read_scene(paths)


def test_meta_round_trips_and_tolerates_a_missing_file(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    assert workspace.read_meta(paths) is None
    workspace.write_meta(paths, {"runId": paths.run_id, "status": "ok"})
    assert workspace.read_meta(paths) == {"runId": paths.run_id, "status": "ok"}


def test_corrupt_meta_reads_as_none(tmp_path: Path):
    paths = workspace.prepare_run(tmp_path, "20260912-153012-a1b2")
    paths.meta.write_text("{ not json", encoding="utf-8")
    assert workspace.read_meta(paths) is None


def test_existing_run_ids_are_newest_first(tmp_path: Path):
    for run_id in ("20260912-100000-0001", "20260912-120000-0002", "20260912-110000-0003"):
        workspace.prepare_run(tmp_path, run_id)
    (tmp_path / "not-a-run").mkdir()
    assert workspace.existing_run_ids(tmp_path) == [
        "20260912-120000-0002",
        "20260912-110000-0003",
        "20260912-100000-0001",
    ]


def test_missing_root_lists_nothing(tmp_path: Path):
    assert workspace.existing_run_ids(tmp_path / "absent") == []


def test_prune_keeps_the_newest_and_reports_deletions(tmp_path: Path):
    ids = ["20260912-100000-0001", "20260912-110000-0002", "20260912-120000-0003"]
    for run_id in ids:
        workspace.prepare_run(tmp_path, run_id)
    removed = workspace.prune_runs(tmp_path, keep=2)
    assert removed == ["20260912-100000-0001"]
    assert workspace.existing_run_ids(tmp_path) == ids[::-1][:2]


def test_prune_with_zero_keeps_everything(tmp_path: Path):
    workspace.prepare_run(tmp_path, "20260912-100000-0001")
    assert workspace.prune_runs(tmp_path, keep=0) == []
    assert workspace.existing_run_ids(tmp_path) == ["20260912-100000-0001"]


def test_prune_is_a_noop_when_under_the_limit(tmp_path: Path):
    workspace.prepare_run(tmp_path, "20260912-100000-0001")
    assert workspace.prune_runs(tmp_path, keep=50) == []


def test_prune_on_a_missing_root_is_a_noop(tmp_path: Path):
    assert workspace.prune_runs(tmp_path / "absent", keep=1) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_workspace.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.engine.workspace'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/engine/workspace.py`:

```python
"""Run-directory lifecycle: naming, layout, metadata, retention.

A run id is the only thing the gallery, the tool envelope, and the on-disk layout
all agree on, so it is generated here and validated everywhere it is accepted.
Names are deliberately ASCII-only: a space, bracket, or CJK character in the path
would break the Markdown image syntax the preview channel depends on.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
META_NAME = "run.json"


class WorkspaceError(RuntimeError):
    """A run directory cannot be prepared or read."""


@dataclass(frozen=True)
class RunPaths:
    """Every path one run owns."""

    run_id: str
    root: Path
    media: Path
    out: Path
    scene: Path

    @property
    def meta(self) -> Path:
        return self.root / META_NAME


def new_run_id(now: datetime | None = None, token: str | None = None) -> str:
    """`YYYYMMDD-HHMMSS-xxxx`, which sorts chronologically as a plain string."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    suffix = token if token is not None else secrets.token_hex(2)
    return f"{stamp}-{suffix}"


def is_valid_run_id(value: str) -> bool:
    return bool(RUN_ID_PATTERN.match(value or ""))


def run_paths(root: Path, run_id: str) -> RunPaths:
    """Describe a run's paths without touching the filesystem."""
    base = root / run_id
    return RunPaths(
        run_id=run_id,
        root=base,
        media=base / "media",
        out=base / "out",
        scene=base / "scene.py",
    )


def prepare_run(root: Path, run_id: str) -> RunPaths:
    """Validate the id and materialise the run tree."""
    if not is_valid_run_id(run_id):
        raise WorkspaceError(
            f"invalid run id {run_id!r}: expected YYYYMMDD-HHMMSS-xxxx "
            "(lowercase hex, ASCII only)"
        )
    paths = run_paths(root, run_id)
    try:
        for directory in (paths.media, paths.out):
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise WorkspaceError(f"cannot create run directory {paths.root}: {error}") from error
    return paths


def write_scene(paths: RunPaths, code: str) -> Path:
    try:
        paths.scene.write_text(code, encoding="utf-8")
    except OSError as error:
        raise WorkspaceError(f"cannot write {paths.scene}: {error}") from error
    return paths.scene


def read_scene(paths: RunPaths) -> str:
    return paths.scene.read_text(encoding="utf-8")


def write_meta(paths: RunPaths, data: dict) -> Path:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        paths.meta.write_text(payload, encoding="utf-8")
    except OSError as error:
        raise WorkspaceError(f"cannot write {paths.meta}: {error}") from error
    return paths.meta


def read_meta_at(run_dir: Path) -> dict | None:
    """Tolerant read: a missing or corrupt run.json is simply absent."""
    try:
        raw = json.loads((run_dir / META_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def read_meta(paths: RunPaths) -> dict | None:
    return read_meta_at(paths.root)


def existing_run_ids(root: Path) -> list[str]:
    """Valid run ids under `root`, newest first. A missing root is empty."""
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    found = [
        child.name
        for child in children
        if child.is_dir() and is_valid_run_id(child.name)
    ]
    found.sort(reverse=True)
    return found


def prune_runs(root: Path, keep: int) -> list[str]:
    """Delete the oldest runs beyond `keep`. `keep <= 0` means keep everything."""
    if keep <= 0:
        return []
    ids = existing_run_ids(root)
    doomed = ids[keep:]
    removed: list[str] = []
    for run_id in doomed:
        try:
            shutil.rmtree(root / run_id, ignore_errors=False)
        except OSError:
            continue
        removed.append(run_id)
    return removed
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_workspace.py -v`
Expected: PASS（15 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/engine/workspace.py tests/test_workspace.py
git commit -m "feat(manim-mcp): run 目录生命周期"
```

---

## Task 5: `engine/index.py` — 动画库索引

**Files:**
- Create: `manim-mcp/manim_mcp/engine/index.py`
- Test: `tests/test_index.py`

- [ ] **Step 1: 写失败测试**

`tests/test_index.py`:

```python
"""The gallery reads index.json, so it must survive every way a file can be wrong."""

import json
import os
from pathlib import Path

from manim_mcp.engine import index, workspace


def _entry(run_id: str, created: str, status: str = "ok") -> dict:
    return {
        "runId": run_id,
        "tool": "equation",
        "status": status,
        "createdAt": created,
        "assets": {"preview": f"D:/r/{run_id}/out/s.gif", "previewKind": "gif"},
        "previewUrlPath": f"/D:/r/{run_id}/out/s.gif",
    }


def test_missing_index_loads_as_empty(tmp_path: Path):
    data = index.load_index(tmp_path)
    assert data["version"] == index.INDEX_VERSION
    assert data["runs"] == []
    assert data["updatedAt"] is None


def test_corrupt_index_loads_as_empty(tmp_path: Path):
    index.index_path(tmp_path).write_text("<<<not json>>>", encoding="utf-8")
    assert index.load_index(tmp_path)["runs"] == []


def test_wrong_shape_loads_as_empty(tmp_path: Path):
    index.index_path(tmp_path).write_text(json.dumps(["a", "list"]), encoding="utf-8")
    assert index.load_index(tmp_path)["runs"] == []


def test_runs_not_a_list_loads_as_empty(tmp_path: Path):
    index.index_path(tmp_path).write_text(json.dumps({"runs": {}}), encoding="utf-8")
    assert index.load_index(tmp_path)["runs"] == []


def test_upsert_appends_and_sorts_newest_first(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    index.upsert_run(tmp_path, _entry("2", "2026-09-12T12:00:00+08:00"))
    index.upsert_run(tmp_path, _entry("3", "2026-09-12T11:00:00+08:00"))
    ids = [run["runId"] for run in index.load_index(tmp_path)["runs"]]
    assert ids == ["2", "3", "1"]


def test_upsert_replaces_the_same_run_id(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00", status="failed"))
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00", status="ok"))
    runs = index.load_index(tmp_path)["runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "ok"


def test_save_stamps_version_and_timestamp(tmp_path: Path):
    data = index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    assert data["version"] == index.INDEX_VERSION
    assert isinstance(data["updatedAt"], str)
    assert data["updatedAt"]


def test_save_leaves_no_temp_file_behind(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_save_replaces_rather_than_truncating_in_place(tmp_path: Path):
    """A reader must never observe a partially written index."""
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    seen: list[str] = []
    real_replace = os.replace

    def spy(src, dst):
        # The destination still holds the previous generation at swap time.
        seen.append(Path(dst).read_text(encoding="utf-8"))
        return real_replace(src, dst)

    os.replace = spy
    try:
        index.upsert_run(tmp_path, _entry("2", "2026-09-12T12:00:00+08:00"))
    finally:
        os.replace = real_replace

    assert len(seen) == 1
    assert json.loads(seen[0])["runs"][0]["runId"] == "1"


def test_remove_drops_only_the_named_run(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    index.upsert_run(tmp_path, _entry("2", "2026-09-12T12:00:00+08:00"))
    data = index.remove_run(tmp_path, "1")
    assert [run["runId"] for run in data["runs"]] == ["2"]


def test_remove_of_an_unknown_run_is_a_noop(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("1", "2026-09-12T10:00:00+08:00"))
    data = index.remove_run(tmp_path, "nope")
    assert [run["runId"] for run in data["runs"]] == ["1"]


def test_rebuild_sorts_and_drops_entries_without_metadata(tmp_path: Path):
    for run_id, created in (
        ("20260912-100000-0001", "2026-09-12T10:00:00+08:00"),
        ("20260912-120000-0002", "2026-09-12T12:00:00+08:00"),
    ):
        paths = workspace.prepare_run(tmp_path, run_id)
        workspace.write_meta(paths, _entry(run_id, created))
    workspace.prepare_run(tmp_path, "20260912-110000-0003")  # no run.json
    (tmp_path / "not-a-run").mkdir()

    data = index.rebuild_index(tmp_path)
    assert [run["runId"] for run in data["runs"]] == [
        "20260912-120000-0002",
        "20260912-100000-0001",
    ]


def test_rebuild_drops_entries_whose_directory_vanished(tmp_path: Path):
    index.upsert_run(tmp_path, _entry("20260912-100000-0001", "2026-09-12T10:00:00+08:00"))
    assert index.rebuild_index(tmp_path)["runs"] == []


def test_rebuild_on_a_missing_root_is_empty(tmp_path: Path):
    assert index.rebuild_index(tmp_path / "absent")["runs"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.engine.index'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/engine/index.py`:

```python
"""The `renders/index.json` catalog.

The gallery panel is a read-only consumer of this file and has no other channel
to the server, so the file must be atomic (a reader never sees half a write) and
totally tolerant (any corruption reads as "no runs yet" rather than raising into
a tool call).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

INDEX_NAME = "index.json"
INDEX_VERSION = 1
TEMP_SUFFIX = ".json.tmp"


def index_path(root: Path) -> Path:
    return root / INDEX_NAME


def empty_index() -> dict:
    return {"version": INDEX_VERSION, "updatedAt": None, "runs": []}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_index(root: Path) -> dict:
    """Never raises: an unreadable or malformed index is an empty index."""
    try:
        raw = json.loads(index_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_index()
    if not isinstance(raw, dict) or not isinstance(raw.get("runs"), list):
        return empty_index()
    raw["version"] = raw.get("version", INDEX_VERSION)
    raw.setdefault("updatedAt", None)
    return raw


def save_index(root: Path, data: dict) -> Path:
    """Publish atomically: write a sibling temp file, then swap it in."""
    target = index_path(root)
    payload = {**data, "version": INDEX_VERSION, "updatedAt": _now_iso()}
    temp = target.with_name(target.name + TEMP_SUFFIX)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp, target)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best effort cleanup
            pass
        raise
    return target


def upsert_run(root: Path, entry: dict) -> dict:
    """Insert or replace one run, keeping the list newest-first."""
    data = load_index(root)
    run_id = entry.get("runId")
    runs = [run for run in data["runs"] if run.get("runId") != run_id]
    runs.append(entry)
    runs.sort(key=lambda run: str(run.get("createdAt") or ""), reverse=True)
    data["runs"] = runs
    save_index(root, data)
    return data


def remove_run(root: Path, run_id: str) -> dict:
    data = load_index(root)
    data["runs"] = [run for run in data["runs"] if run.get("runId") != run_id]
    save_index(root, data)
    return data


def rebuild_index(root: Path) -> dict:
    """Reconcile the index against the run directories actually on disk.

    The on-disk tree wins: an entry whose directory is gone is dropped, and a
    directory whose metadata is unreadable is skipped rather than invented.
    """
    from . import workspace

    entries: list[dict] = []
    for run_id in workspace.existing_run_ids(root):
        meta = workspace.read_meta_at(root / run_id)
        if meta is None:
            continue
        meta.setdefault("runId", run_id)
        entries.append(meta)

    entries.sort(key=lambda run: str(run.get("createdAt") or ""), reverse=True)
    data = {"version": INDEX_VERSION, "updatedAt": None, "runs": entries}
    if entries or index_path(root).exists():
        save_index(root, data)
    return load_index(root)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_index.py -v`
Expected: PASS（14 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/engine/index.py tests/test_index.py
git commit -m "feat(manim-mcp): 动画库索引"
```

---

## Task 6: `engine/diagnostics.py` — 从 stderr 到可执行建议

**Files:**
- Create: `manim-mcp/manim_mcp/engine/diagnostics.py`
- Test: `tests/test_diagnostics.py`
- Create: `tests/fixtures/manim_nameerror.txt`
- Create: `tests/fixtures/manim_latex_error.txt`

- [ ] **Step 1: 写测试样本**

`tests/fixtures/manim_nameerror.txt`（真实的 Manim stderr 摘录，含 ANSI、进度噪声与那行无害的 RuntimeWarning）：

```
Manim Community v0.20.1

<frozen runpy>:128: RuntimeWarning: 'manim.__main__' found in sys.modules after import of package 'manim', but prior to execution of 'manim.__main__'; this may result in unpredictable behaviour
Traceback (most recent call last):
  File "D:\myprogram\dshplugin\renders\20260912-153012-a1b2\scene.py", line 12, in <module>
    Smoke().render()
  File "D:\myprogram\dshplugin\renders\20260912-153012-a1b2\scene.py", line 9, in construct
    circle = Circle(radius=1)
             ^^^^^^^^^^^^^^^^
NameError: name 'Circle' is not defined
```

`tests/fixtures/manim_latex_error.txt`：

```
Manim Community v0.20.1

[09/12/26 15:30:12] INFO     Writing tex file                               tex_file_writing.py:243
Traceback (most recent call last):
  File "D:\myprogram\dshplugin\renders\20260912-153012-a1b2\scene.py", line 6, in construct
    formula = MathTex(r"\undefinedmacro{x}")
  File "D:\ProgramData\anaconda3\Lib\site-packages\manim\mobject\svg\tex_mobject.py", line 200, in __init__
    self.tex_strings = self._break_up_tex_strings(tex_strings)
  File "D:\ProgramData\anaconda3\Lib\site-packages\manim\utils\tex_file_writing.py", line 280, in print_all_tex_errors
    raise RuntimeError(
RuntimeError: latex failed but did not produce a log file. Check your LaTeX installation.
```

- [ ] **Step 2: 写失败测试**

`tests/test_diagnostics.py`:

```python
"""stderr is the only ground truth after a failed render; parse it honestly."""

from pathlib import Path

from manim_mcp.engine import diagnostics

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCENE = Path(r"D:\myprogram\dshplugin\renders\20260912-153012-a1b2\scene.py")


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_strip_noise_removes_ansi_and_the_manim_runtime_warning():
    cleaned = diagnostics.strip_noise(read("manim_nameerror.txt"))
    assert "\x1b" not in cleaned
    assert "RuntimeWarning: 'manim.__main__'" not in cleaned
    assert "NameError: name 'Circle' is not defined" in cleaned


def test_strip_noise_removes_progress_lines():
    raw = "Rendering 12/40\nAnimation 3: Write\n12%|█   | 12/100\nreal content\n"
    cleaned = diagnostics.strip_noise(raw)
    assert "real content" in cleaned
    assert "12%|" not in cleaned


def test_parse_finds_the_frame_in_the_scene_file():
    exc_type, message, line = diagnostics.parse_traceback(
        diagnostics.strip_noise(read("manim_nameerror.txt")), SCENE
    )
    assert exc_type == "NameError"
    assert message == "name 'Circle' is not defined"
    assert line == 9


def test_parse_prefers_the_scene_file_over_library_frames():
    exc_type, _, line = diagnostics.parse_traceback(
        diagnostics.strip_noise(read("manim_latex_error.txt")), SCENE
    )
    assert exc_type == "RuntimeError"
    assert line == 6


def test_parse_returns_nothing_when_there_is_no_traceback():
    assert diagnostics.parse_traceback("just some noise\n", SCENE) == (None, None, None)


def test_classify_reads_the_offending_source_line(tmp_path: Path):
    scene = tmp_path / "scene.py"
    scene.write_text(
        "from manim import *\n"
        "\n"
        "class Smoke(Scene):\n"
        "    def construct(self):\n"
        "        circle = Circle(radius=1)\n",
        encoding="utf-8",
    )
    raw = read("manim_nameerror.txt").replace(str(SCENE), str(scene)).replace(
        "line 9", "line 5"
    )
    result = diagnostics.classify(raw, scene, stage="manim")
    assert result.stage == "manim"
    assert result.type == "NameError"
    assert result.line == 5
    assert result.source_line == "        circle = Circle(radius=1)"
    assert "from manim import *" in result.hint


def test_hint_for_nameerror_names_the_missing_symbol():
    hint = diagnostics.hint_for("NameError", "name 'Circle' is not defined", "")
    assert "Circle" in hint
    assert "from manim import *" in hint


def test_hint_for_latex_failure():
    hint = diagnostics.hint_for(
        "RuntimeError", "latex failed but did not produce a log file.", "LaTeX Error"
    )
    assert "LaTeX" in hint
    assert "MathTex" in hint


def test_hint_for_animate_misuse():
    hint = diagnostics.hint_for(
        "AttributeError",
        "'Circle' object has no attribute 'shift'",
        "ValueError: Please use ... .animate syntax",
    )
    assert ".animate" in hint


def test_hint_for_missing_latex_binary():
    hint = diagnostics.hint_for(
        "FileNotFoundError", "[Errno 2] No such file or directory: 'latex'", ""
    )
    assert "MiKTeX" in hint


def test_hint_for_unpack_error():
    hint = diagnostics.hint_for(
        "ValueError", "too many values to unpack (expected 2)", ""
    )
    assert "参数" in hint


def test_hint_is_none_for_an_unrecognised_failure():
    assert diagnostics.hint_for("KeyError", "42", "") is None


def test_tail_keeps_the_end_and_marks_truncation():
    tail = diagnostics.tail("x" * 100, max_chars=10)
    assert tail.endswith("x" * 10)
    assert "100" in tail
    assert diagnostics.tail("short", max_chars=100) == "short"


def test_classify_without_a_traceback_still_reports_stderr():
    result = diagnostics.classify("boom\n", SCENE, stage="manim")
    assert result.type is None
    assert result.hint is None
    assert "boom" in result.stderr_tail
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_diagnostics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.engine.diagnostics'`

- [ ] **Step 4: 写实现**

`manim-mcp/manim_mcp/engine/diagnostics.py`:

```python
"""Turn raw subprocess stderr into one actionable Diagnostic.

A failed render is only useful to the model if it can act on it, so the goal is
never to forward a blob: it is to name the exception, the line in *its own* file,
that line's source, and the specific edit that most often fixes it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
RUNTIME_WARNING_RE = re.compile(
    r"^.*RuntimeWarning: 'manim\.__main__'.*(?:\n\s+.*)*$", re.MULTILINE
)
PROGRESS_RE = re.compile(
    r"^\s*(?:Rendering\s|Animation\s|Playing\s|\d+%\|).*$", re.MULTILINE
)
FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>.+)$', re.MULTILINE
)
EXCEPTION_RE = re.compile(
    r"^(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt|Warning)?): "
    r"(?P<message>.+)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Diagnostic:
    """What went wrong, where, and what to try instead."""

    stage: str
    type: str | None = None
    message: str | None = None
    line: int | None = None
    source_line: str | None = None
    hint: str | None = None
    stderr_tail: str = ""

    def as_dict(self) -> dict:
        payload = {"stage": self.stage}
        for key in ("type", "message", "line", "sourceLine", "hint"):
            value = getattr(self, key if key != "sourceLine" else "source_line")
            if value is not None:
                payload[key] = value
        payload["stderrTail"] = self.stderr_tail
        return payload


def strip_noise(text: str) -> str:
    """Drop ANSI, progress rows, and the harmless runpy warning."""
    cleaned = ANSI_RE.sub("", text or "")
    cleaned = RUNTIME_WARNING_RE.sub("", cleaned)
    cleaned = PROGRESS_RE.sub("", cleaned)
    return cleaned


def tail(text: str, max_chars: int = 4000) -> str:
    """The end of a long log, with an explicit marker when it was cut."""
    body = text or ""
    if len(body) <= max_chars:
        return body
    return f"...[{len(body)} chars truncated]...\n{body[-max_chars:]}"


def parse_traceback(text: str, scene_file: str | Path) -> tuple[str | None, str | None, int | None]:
    """Extract (exception type, message, line).

    Prefers the last frame inside the generated scene over library frames, so the
    reported line is one the model can actually edit.
    """
    frames = list(FRAME_RE.finditer(text or ""))
    if not frames:
        return None, None, None

    wanted = Path(str(scene_file)).name
    chosen = frames[-1]
    for frame in frames:
        if Path(frame.group("file")).name == wanted:
            chosen = frame

    exc_type: str | None = None
    message: str | None = None
    match = EXCEPTION_RE.search(text[chosen.end():])
    if match:
        exc_type = match.group("type")
        message = match.group("message").strip()
    return exc_type, message, int(chosen.group("line"))


def _source_line(scene_file: str | Path, line: int | None) -> str | None:
    if line is None:
        return None
    try:
        lines = Path(scene_file).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()
    return None


def hint_for(exception_type: str | None, message: str | None, blob: str) -> str | None:
    """The single most likely fix, or None when the failure is unfamiliar."""
    etype = (exception_type or "").casefold()
    text = (message or "").casefold()
    whole = (blob or "").casefold()

    if etype.endswith("nameerror"):
        match = re.search(r"name '([^']+)'", message or "")
        symbol = match.group(1) if match else "该名字"
        return (
            f"`{symbol}` 未定义。生成的代码开头需要 `from manim import *`；"
            "如果这是你自己命名的变量，检查它是否在使用之前就完成了赋值。"
        )

    if "latex" in whole and (
        "latex error" in whole or "did not produce a log file" in whole
    ):
        return (
            "LaTeX 编译失败：检查公式里的反斜杠转义是否在 Python 字符串里被吃掉，"
            "避免使用未安装宏包提供的命令，并确认数学内容用的是 `MathTex` 而不是 `Tex`。"
        )

    if etype.endswith("filenotfounderror") and ("latex" in whole or "dvisvgm" in whole):
        return "找不到 LaTeX 工具链：确认 MiKTeX 已安装，且 `latex` 与 `dvisvgm` 在 PATH 上。"

    if etype.endswith("attributeerror") and ".animate" in whole:
        return (
            "`.animate` 用法有误：写成 `mob.animate.shift(...)`，"
            "并把这个表达式整体作为 `self.play(...)` 的参数，不要把它先赋值再调用别的方法。"
        )

    if "font" in text or ("font" in whole and "not found" in whole):
        return "字体不可用：改用 `style_guide` 返回的本机中文字体名，或直接使用 `cn()` 辅助函数。"

    if etype.endswith("valueerror") and "too many values to unpack" in text:
        return "Mobject 构造参数个数不对：检查该图形类的必填参数数量。"

    return None


def classify(stderr: str, scene_file: str | Path, stage: str = "manim") -> Diagnostic:
    """One pass from raw stderr to a Diagnostic."""
    cleaned = strip_noise(stderr)
    exc_type, message, line = parse_traceback(cleaned, scene_file)
    return Diagnostic(
        stage=stage,
        type=exc_type,
        message=message,
        line=line,
        source_line=_source_line(scene_file, line),
        hint=hint_for(exc_type, message, cleaned),
        stderr_tail=tail(cleaned),
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_diagnostics.py -v`
Expected: PASS（15 passed）

- [ ] **Step 6: 提交**

```bash
git add manim-mcp/manim_mcp/engine/diagnostics.py tests/test_diagnostics.py tests/fixtures
git commit -m "feat(manim-mcp): 渲染失败诊断与修复提示"
```

---

## Task 7: `engine/postprocess.py` — 预览与体积降级链

**Files:**
- Create: `manim-mcp/manim_mcp/engine/postprocess.py`
- Test: `tests/test_postprocess.py`

- [ ] **Step 1: 写失败测试**

`tests/test_postprocess.py`:

```python
"""The size ladder is the only thing standing between a render and a 20 MiB cap."""

import subprocess
from pathlib import Path

from manim_mcp.engine import postprocess

FFMPEG = r"D:\tools\ffmpeg.exe"


class FakeFFmpeg:
    """Records every invocation and fabricates outputs of a prescribed size."""

    def __init__(self, sizes: dict[str, int], duration: str = "00:00:10.00"):
        self.sizes = sizes
        self.duration = duration
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[0] != FFMPEG:
            raise AssertionError(f"unexpected binary {argv[0]!r}")

        if "-y" not in argv and "-i" in argv and argv[-1] != "-":
            # probe_duration / poster extraction shape
            return subprocess.CompletedProcess(argv, 1, "", f"  Duration: {self.duration}, start: 0")

        out = Path(argv[-1])
        kind = out.suffix.lstrip(".")
        size = self.sizes.get(f"{kind}:{self._tag(argv)}", self.sizes.get(kind, 1024))
        if kind in {"gif", "webp", "png"}:
            out.write_bytes(b"x" * size)
        return subprocess.CompletedProcess(argv, 0, "", "")

    @staticmethod
    def _tag(argv: list[str]) -> str:
        for item in argv:
            if isinstance(item, str) and item.startswith("fps="):
                fps = item.split(",")[0].split("=")[1]
                for other in argv:
                    if isinstance(other, str) and other.startswith("scale="):
                        width = other.split(",")[1].split(":")[0].split("=")[1]
                        return f"{fps}@{width}"
        return "default"


def test_probe_duration_parses_ffmpeg_output(tmp_path: Path):
    fake = FakeFFmpeg({}, duration="00:00:12.40")
    assert postprocess.probe_duration(FFMPEG, tmp_path / "a.mp4", run=fake) == 12.4


def test_probe_duration_returns_zero_when_unparseable(tmp_path: Path):
    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "no duration here")

    assert postprocess.probe_duration(FFMPEG, tmp_path / "a.mp4", run=runner) == 0.0


def test_short_scene_returns_the_poster_frame(tmp_path: Path):
    fake = FakeFFmpeg({"png": 4096}, duration="00:00:00.40")
    preview = postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    assert preview.kind == "png"
    assert preview.path == tmp_path / "Scene.png"
    assert preview.byte_size == 4096
    assert any("静态" in note for note in preview.warnings)


def test_first_ladder_rung_is_used_when_it_fits(tmp_path: Path):
    fake = FakeFFmpeg({"gif": 500_000}, duration="00:00:10.00")
    preview = postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    assert preview.kind == "gif"
    assert preview.byte_size == 500_000
    assert preview.warnings == ()


def test_overshoot_of_the_target_is_reported_but_accepted(tmp_path: Path):
    fake = FakeFFmpeg({"gif": 1_500_000}, duration="00:00:10.00")
    preview = postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    assert preview.kind == "gif"
    assert any("目标体积" in note for note in preview.warnings)


def test_ladder_degrades_fps_and_width_before_giving_up(tmp_path: Path):
    sizes = {"gif:15@800": 2_100_000, "gif:12@800": 2_100_000, "gif:12@640": 900_000}
    fake = FakeFFmpeg(sizes, duration="00:00:10.00")
    preview = postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    assert preview.kind == "gif"
    assert preview.byte_size == 900_000
    ladder = [postprocess._to_fps_and_width(call) for call in fake.calls if any(
        isinstance(a, str) and a.startswith("fps=") for a in call
    )]
    assert ladder[:3] == [(15, 800), (12, 800), (12, 640)]


def test_falls_back_to_webp_when_every_gif_rung_overshoots(tmp_path: Path):
    sizes = {"gif": 3_000_000, "webp": 400_000}
    fake = FakeFFmpeg(sizes, duration="00:00:10.00")
    preview = postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    assert preview.kind == "webp"
    assert preview.byte_size == 400_000
    assert preview.path is not None and preview.path.suffix == ".webp"


def test_falls_back_to_the_poster_when_both_formats_overshoot(tmp_path: Path):
    sizes = {"gif": 3_000_000, "webp": 3_000_000, "png": 50_000}
    fake = FakeFFmpeg(sizes, duration="00:00:10.00")
    preview = postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    assert preview.kind == "png"
    assert preview.byte_size == 50_000
    assert any("硬上限" in note for note in preview.warnings)


def test_overshooting_artifacts_are_deleted(tmp_path: Path):
    sizes = {"gif": 3_000_000, "webp": 3_000_000, "png": 50_000}
    fake = FakeFFmpeg(sizes, duration="00:00:10.00")
    postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    assert not (tmp_path / "Scene.gif").exists()
    assert not (tmp_path / "Scene.webp").exists()


def test_poster_is_taken_from_the_last_frame(tmp_path: Path):
    fake = FakeFFmpeg({"png": 1024}, duration="00:00:10.00")
    postprocess.build_preview(
        FFMPEG, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000, run=fake,
    )
    poster_call = [call for call in fake.calls if call[-1].endswith("Scene.png")][0]
    assert "-sseof" in poster_call


def test_missing_ffmpeg_yields_no_preview(tmp_path: Path):
    preview = postprocess.build_preview(
        None, tmp_path / "a.mp4", tmp_path, "Scene",
        target_bytes=1_000_000, max_bytes=2_000_000,
    )
    assert preview.path is None
    assert preview.kind is None
    assert any("ffmpeg" in note for note in preview.warnings)


def test_mime_lookup_covers_every_preview_kind():
    assert postprocess.MIME_BY_KIND == {
        "gif": "image/gif",
        "webp": "image/webp",
        "png": "image/png",
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_postprocess.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.engine.postprocess'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/engine/postprocess.py`:

```python
"""MP4 → animated GIF / WebP / PNG preview, with an honest size ladder.

DSH's `/api/file` serves at most 20 MiB per file, and an oversized preview is a
silent failure for the user. So the encoder walks a fixed ladder, and when GIF
cannot get under the cap at any rung it moves to WebP before finally settling on
a single poster frame.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# (fps, width) tried in order. Later rungs trade smoothness for resolution.
LADDER: tuple[tuple[int, int], ...] = ((15, 800), (12, 800), (12, 640), (10, 480))
ANIMATED_KINDS = ("gif", "webp")
STATIC_SECONDS = 1.0
PROBE_TIMEOUT_SEC = 60
ENCODE_TIMEOUT_SEC = 180

DURATION_RE = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")
FPS_WIDTH_RE = re.compile(r"fps=(\d+).*?scale=(\d+)", re.DOTALL)

MIME_BY_KIND = {"gif": "image/gif", "webp": "image/webp", "png": "image/png"}


@dataclass(frozen=True)
class Preview:
    """The preview artifact, or an explicit absence with a reason."""

    path: Path | None
    kind: str | None
    byte_size: int
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _run(argv: list[str], *, timeout: int, run=None) -> subprocess.CompletedProcess:
    runner = run or subprocess.run
    return runner(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def probe_duration(ffmpeg: str, mp4: Path, *, run=None) -> float:
    """Seconds of video, or 0.0 when ffmpeg cannot say.

    ffmpeg has no "print metadata" mode, so we let it fail on the missing output
    and read the duration out of its banner.
    """
    result = _run([ffmpeg, "-hide_banner", "-i", str(mp4)], timeout=PROBE_TIMEOUT_SEC, run=run)
    match = DURATION_RE.search(result.stderr or "")
    if match is None:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_poster(ffmpeg: str, mp4: Path, out_png: Path, *, run=None) -> Path:
    """The *last* frame: an animation's final state is its conclusion."""
    _run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-sseof", "-0.1", "-i", str(mp4),
            "-frames:v", "1", str(out_png),
        ],
        timeout=ENCODE_TIMEOUT_SEC,
        run=run,
    )
    return out_png


def encode_animated(
    ffmpeg: str, mp4: Path, out: Path, fps: int, width: int, kind: str, *, run=None
) -> Path:
    """Encode one rung of the ladder."""
    if kind == "gif":
        palette = out.with_suffix(".palette.png")
        _run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4),
                "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,palettegen=stats_mode=diff",
                str(palette),
            ],
            timeout=ENCODE_TIMEOUT_SEC,
            run=run,
        )
        _run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(mp4), "-i", str(palette),
                "-lavfi",
                f"fps={fps},scale={width}:-1:flags=lanczos[x];"
                "[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                str(out),
            ],
            timeout=ENCODE_TIMEOUT_SEC,
            run=run,
        )
        palette.unlink(missing_ok=True)
        return out

    _run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4),
            "-vf", f"fps={fps},scale={width}:-1:flags=lanczos",
            "-c:v", "libwebp", "-lossless", "0", "-q:v", "70", "-loop", "0",
            str(out),
        ],
        timeout=ENCODE_TIMEOUT_SEC,
        run=run,
    )
    return out


def build_preview(
    ffmpeg: str | None,
    mp4: Path,
    out_dir: Path,
    basename: str,
    *,
    target_bytes: int,
    max_bytes: int,
    run=None,
) -> Preview:
    """Produce the smallest acceptable preview for `mp4`."""
    if not ffmpeg:
        return Preview(
            path=None,
            kind=None,
            byte_size=0,
            warnings=("ffmpeg 不可用，未生成预览图",),
        )

    poster = out_dir / f"{basename}.png"
    duration = probe_duration(ffmpeg, mp4, run=run)
    extract_poster(ffmpeg, mp4, poster, run=run)

    if duration < STATIC_SECONDS:
        size = poster.stat().st_size if poster.exists() else 0
        return Preview(
            path=poster if poster.exists() else None,
            kind="png" if poster.exists() else None,
            byte_size=size,
            warnings=(f"静态场景（{duration:.2f}s）：只输出海报帧",),
        )

    for kind in ANIMATED_KINDS:
        for fps, width in LADDER:
            out = out_dir / f"{basename}.{kind}"
            encode_animated(ffmpeg, mp4, out, fps, width, kind, run=run)
            size = out.stat().st_size if out.exists() else 0
            if size and size <= max_bytes:
                warnings: tuple[str, ...] = ()
                if size > target_bytes:
                    warnings = (f"{kind} 超过目标体积 {target_bytes}B，实际 {size}B",)
                return Preview(path=out, kind=kind, byte_size=size, warnings=warnings)
            out.unlink(missing_ok=True)

    poster_size = poster.stat().st_size if poster.exists() else 0
    return Preview(
        path=poster if poster.exists() else None,
        kind="png" if poster.exists() else None,
        byte_size=poster_size,
        warnings=(
            f"GIF 与 WebP 在全部降级档位下都超过硬上限 {max_bytes}B，已降级为海报帧",
        ),
    )


def _to_fps_and_width(argv: list[str]) -> tuple[int, int] | None:
    """Test helper: recover the ladder rung an ffmpeg invocation used."""
    for item in argv:
        if isinstance(item, str) and item.startswith("fps="):
            match = FPS_WIDTH_RE.search(item)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_postprocess.py -v`
Expected: PASS（12 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/engine/postprocess.py tests/test_postprocess.py
git commit -m "feat(manim-mcp): 预览后处理与体积降级链"
```

---

## Task 8: `engine/render.py` — manim 子进程

**Files:**
- Create: `manim-mcp/manim_mcp/engine/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: 写失败测试**

`tests/test_render.py`:

```python
"""Rendering is a subprocess contract: argv, timeout, kill, artifact discovery."""

import subprocess
from datetime import datetime
from pathlib import Path

from manim_mcp.config import Config
from manim_mcp.engine import render, workspace


def make_config(**overrides) -> Config:
    base = dict(
        python=r"D:\py\python.exe",
        manim=None,
        ffmpeg=r"D:\tools\ffmpeg.exe",
        render_root=Path("."),
        max_concurrency=1,
        timeout_sec=1.0,
        gif_target_bytes=100,
        gif_max_bytes=200,
        keep_runs=1,
        log_level="INFO",
    )
    base.update(overrides)
    return Config(**base)


def make_run(tmp_path: Path):
    return workspace.prepare_run(tmp_path, "20260912-153012-a1b2")


class FakeProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.pid = 4242
        self.killed = False
        self.timeouts: list[float] = []
        self._polls = 0

    def communicate(self, timeout=None):
        if timeout is not None:
            self.timeouts.append(timeout)
            if getattr(self, "hang", False) and not self.killed:
                raise subprocess.TimeoutExpired(cmd="manim", timeout=timeout)
        return self.stdout, self.stderr

    def poll(self):
        return None if getattr(self, "hang", False) and not self.killed else self.returncode

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


def test_argv_uses_the_module_form_when_no_binary_is_pinned(tmp_path: Path):
    paths = make_run(tmp_path)
    argv = render.build_argv(make_config(), paths, "EquationScene", "draft")
    assert argv[:3] == [r"D:\py\python.exe", "-m", "manim"]
    assert argv[3] == "render"
    assert "-ql" in argv
    assert "--format=mp4" in argv
    assert str(paths.media) in argv
    assert argv[-1] == "EquationScene"


def test_argv_uses_the_pinned_binary_when_present(tmp_path: Path):
    paths = make_run(tmp_path)
    cfg = make_config(manim=r"D:\py\Scripts\manim.exe")
    argv = render.build_argv(cfg, paths, "EquationScene", "final")
    assert argv[0] == r"D:\py\Scripts\manim.exe"
    assert "-qm" in argv


def test_final_quality_uses_the_720p_flag(tmp_path: Path):
    paths = make_run(tmp_path)
    assert "-qm" in render.build_argv(make_config(), paths, "S", "final")


def test_successful_render_reports_the_mp4(tmp_path: Path):
    paths = make_run(tmp_path)
    imported = paths.media / "videos" / "scene" / "480p15" / "EquationScene.mp4"
    imported.parent.mkdir(parents=True)

    captured = {}

    def popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        imported.write_bytes(b"mp4")
        return FakeProcess(returncode=0)

    result = render.render_scene(make_config(), paths, "EquationScene", "draft", popen=popen)
    assert result.ok is True
    assert result.mp4 == imported
    assert result.diagnostic is None
    assert result.seconds >= 0
    assert captured["kwargs"]["text"] is True


def test_failing_render_returns_a_diagnostic(tmp_path: Path):
    paths = make_run(tmp_path)
    workspace.write_scene(
        paths, "from manim import *\n\nclass S(Scene):\n    def construct(self):\n        x = Nope()\n"
    )
    stderr = (
        "Traceback (most recent call last):\n"
        f'  File "{paths.scene}", line 5, in construct\n'
        "    x = Nope()\n"
        "NameError: name 'Nope' is not defined\n"
    )

    def popen(argv, **kwargs):
        return FakeProcess(returncode=1, stderr=stderr)

    result = render.render_scene(make_config(), paths, "S", "draft", popen=popen)
    assert result.ok is False
    assert result.mp4 is None
    assert result.diagnostic is not None
    assert result.diagnostic.type == "NameError"
    assert result.diagnostic.line == 5


def test_exit_zero_without_an_artifact_is_a_failure(tmp_path: Path):
    paths = make_run(tmp_path)

    def popen(argv, **kwargs):
        return FakeProcess(returncode=0)

    result = render.render_scene(make_config(), paths, "S", "draft", popen=popen)
    assert result.ok is False
    assert result.diagnostic is not None
    assert "产物" in (result.diagnostic.message or "")


def test_timeout_kills_the_process_tree_and_reports_timeout(tmp_path: Path):
    paths = make_run(tmp_path)
    process = FakeProcess(returncode=1, stderr="still working")
    process.hang = True
    killed: list[list[str]] = []

    def popen(argv, **kwargs):
        return process

    def run(argv, **kwargs):
        killed.append(list(argv))
        process.kill()
        return subprocess.CompletedProcess(argv, 0, "", "")

    result = render.render_scene(
        make_config(timeout_sec=2.0), paths, "S", "draft", popen=popen, run=run
    )
    assert result.ok is False
    assert result.diagnostic is not None
    assert result.diagnostic.stage == "timeout"
    assert "2" in (result.diagnostic.message or "")
    assert any(argv[0] == "taskkill" for argv in killed) or process.killed


def test_missing_artifact_search_returns_none(tmp_path: Path):
    assert render.find_output_mp4(tmp_path, "Nothing") is None


def test_artifact_search_prefers_the_newest_match(tmp_path: Path):
    base = tmp_path / "videos" / "scene" / "480p15"
    base.mkdir(parents=True)
    older = base / "S.mp4"
    older.write_bytes(b"old")
    import os
    import time

    time.sleep(0.01)
    newer = tmp_path / "videos" / "scene" / "720p30"
    newer.mkdir(parents=True)
    fresh = newer / "S.mp4"
    fresh.write_bytes(b"new")
    os.utime(older, (1, 1))
    assert render.find_output_mp4(tmp_path, "S") == fresh
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.engine.render'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/engine/render.py`:

```python
"""Invoke the Manim CLI and collect its artifact.

The child is spawned in its own process group so a timeout can take down the
whole tree: Manim forks `latex`, `dvisvgm`, and `ffmpeg`, and killing only the
parent would leave those holding the CPU and the output files.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .. import config as config_mod
from . import diagnostics

QUALITY_FLAG = {"draft": "-ql", "final": "-qm"}

KILL_TIMEOUT_SEC = 10


@dataclass(frozen=True)
class RenderResult:
    """Outcome of one Manim invocation."""

    ok: bool
    mp4: Path | None
    seconds: float
    diagnostic: diagnostics.Diagnostic | None = None


def build_argv(cfg: config_mod.Config, paths, scene_name: str, quality: str) -> list[str]:
    """The exact command line for one render."""
    flag = QUALITY_FLAG.get(quality)
    if flag is None:
        raise ValueError(f"unknown quality {quality!r}; expected one of {sorted(QUALITY_FLAG)}")
    return config_mod.manim_argv(
        cfg,
        "render",
        flag,
        "--format=mp4",
        "--media_dir", str(paths.media),
        "--output_file", scene_name,
        str(paths.scene),
        scene_name,
    )


def find_output_mp4(media_dir: Path, scene_name: str) -> Path | None:
    """Newest `videos/**/<scene>.mp4` under the media dir, or None.

    The intermediate directories encode the module stem and the quality label, so
    globbing is more durable than reconstructing that path.
    """
    try:
        candidates = [p for p in media_dir.glob(f"videos/**/{scene_name}.mp4") if p.is_file()]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _kill_tree(process, run=None) -> None:
    """Terminate the child and everything it spawned."""
    if process.poll() is not None:
        return
    runner = run or subprocess.run
    if os.name == "nt":
        try:
            runner(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
        except OSError:  # pragma: no cover - taskkill is present on Windows
            process.kill()
    else:  # pragma: no cover - the deployment target is Windows
        process.kill()
    try:
        process.wait(timeout=KILL_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        pass


def render_scene(
    cfg: config_mod.Config,
    paths,
    scene_name: str,
    quality: str,
    *,
    popen=None,
    run=None,
) -> RenderResult:
    """Render one scene, converting every failure mode into a RenderResult."""
    argv = build_argv(cfg, paths, scene_name, quality)
    spawn = popen or subprocess.Popen
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0

    started = time.monotonic()
    process = spawn(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )

    timed_out = False
    try:
        _, stderr = process.communicate(timeout=cfg.timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(process, run=run)
        try:
            _, stderr = process.communicate(timeout=KILL_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            stderr = ""
    elapsed = time.monotonic() - started

    if timed_out:
        return RenderResult(
            ok=False,
            mp4=None,
            seconds=elapsed,
            diagnostic=diagnostics.Diagnostic(
                stage="timeout",
                message=f"渲染超过 {cfg.timeout_sec:g} 秒，进程树已终止",
                stderr_tail=diagnostics.tail(diagnostics.strip_noise(stderr or "")),
            ),
        )

    mp4 = find_output_mp4(paths.media, scene_name)
    if process.returncode == 0 and mp4 is not None:
        return RenderResult(ok=True, mp4=mp4, seconds=elapsed)

    if process.returncode == 0:
        return RenderResult(
            ok=False,
            mp4=None,
            seconds=elapsed,
            diagnostic=diagnostics.Diagnostic(
                stage="manim",
                message=(
                    f"manim 退出码为 0，但没有找到产物 {scene_name}.mp4"
                    "（通常是场景类没有被真正执行）"
                ),
                stderr_tail=diagnostics.tail(diagnostics.strip_noise(stderr or "")),
            ),
        )

    diagnostic = diagnostics.classify(stderr or "", paths.scene, stage="manim")
    if diagnostic.type is None:
        diagnostic = diagnostics.Diagnostic(
            stage="manim",
            message=f"manim 退出码 {process.returncode}",
            stderr_tail=diagnostic.stderr_tail,
        )
    return RenderResult(ok=False, mp4=mp4, seconds=elapsed, diagnostic=diagnostic)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_render.py -v`
Expected: PASS（10 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/engine/render.py tests/test_render.py
git commit -m "feat(manim-mcp): manim 子进程封装"
```

---

## Task 9: `scenes` 注册表与 `equation` 模板

**Files:**
- Modify: `manim-mcp/manim_mcp/scenes/__init__.py`
- Create: `manim-mcp/manim_mcp/scenes/equation.py`
- Test: `tests/test_scenes_registry.py`
- Test: `tests/test_scene_equation.py`

- [ ] **Step 1: 写失败测试**

`tests/test_scenes_registry.py`:

```python
"""Every template is reachable by name and validates before it emits source."""

import ast

import pytest

from manim_mcp import scenes


def test_registry_exposes_exactly_the_four_templates():
    assert sorted(scenes.registry()) == ["compare", "diagram", "equation", "graph"]


def test_every_template_compiles_and_declares_a_scene_class():
    assert all(template.scene_class for template in scenes.registry().values())
    assert all(template.summary for template in scenes.registry().values())


def test_unknown_template_is_rejected():
    with pytest.raises(scenes.SceneSpecError) as caught:
        scenes.build("nope")
    assert "nope" in str(caught.value)
    assert "equation" in str(caught.value)


def test_build_returns_class_and_compilable_source():
    scene_class, code = scenes.build("equation", steps=[r"a=b", r"a=c"])
    assert scene_class == "EquationScene"
    ast.parse(code)


def test_build_rejects_bad_template_arguments():
    with pytest.raises(scenes.SceneSpecError):
        scenes.build("equation", steps=[r"a=b"])


def test_catalogue_is_serialisable_for_the_style_guide():
    catalogue = scenes.catalogue()
    assert isinstance(catalogue, list)
    assert {row["name"] for row in catalogue} == set(scenes.registry())
    assert all(isinstance(row["params"], dict) for row in catalogue)
```

`tests/test_scene_equation.py`:

```python
"""The equation template is 3b1b's signature move; it must emit valid source."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("equation", **kwargs)


def test_minimal_two_step_scene_compiles():
    scene_class, code = build(steps=[r"a = b", r"a = c"])
    assert scene_class == "EquationScene"
    ast.parse(code)
    assert r'"a = c"' in code


def test_steps_are_emitted_as_python_string_literals():
    _, code = build(steps=[r"\frac{1}{2}", r"\frac{2}{4}"])
    ast.parse(code)
    assert r'"\\frac{1}{2}"' in code


def test_unicode_steps_survive_codegen():
    _, code = build(steps=["能量 = 质量", "E = mc^2"])
    ast.parse(code)
    assert "能量 = 质量" in code


def test_title_switches_on_the_title_block_with_the_cjk_helper():
    _, code = build(title="欧拉恒等式", steps=[r"e^{i\pi}", r"-1"])
    ast.parse(code)
    assert "cn(" in code
    assert "欧拉恒等式" in code
    assert "HAS_TITLE = True" in code


def test_absent_title_switches_the_block_off():
    _, code = build(steps=[r"a", r"b"])
    ast.parse(code)
    assert "HAS_TITLE = False" in code


def test_highlight_length_must_match_steps():
    with pytest.raises(SceneSpecError) as caught:
        build(steps=[r"a", r"b"], highlight=["a"])
    assert "highlight" in str(caught.value)


def test_highlight_is_applied_per_step():
    _, code = build(steps=[r"a = b", r"a = c"], highlight=["b", "c"])
    ast.parse(code)
    assert "HAS_HIGHLIGHT = True" in code
    assert "set_color_by_tex" in code


def test_single_step_is_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[r"a"])


def test_seven_steps_are_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[f"x_{i}" for i in range(7)])


def test_empty_step_is_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[r"a", "   "])


def test_non_string_step_is_rejected():
    with pytest.raises(SceneSpecError):
        build(steps=[r"a", 42])


def test_steps_must_be_a_sequence():
    with pytest.raises(SceneSpecError):
        build(steps="a=b")


def test_missing_steps_is_rejected():
    with pytest.raises(SceneSpecError):
        build()


def test_preamble_carries_the_palette_and_the_font():
    _, code = build(steps=[r"a", r"b"], cjk_font="SimHei")
    assert 'config.background_color = "#0E1116"' in code
    assert 'FONT_CJK = "SimHei"' in code
    assert "from manim import *" in code
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_scenes_registry.py tests/test_scene_equation.py -v`
Expected: FAIL — `ImportError: cannot import name 'registry' from 'manim_mcp.scenes'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/scenes/__init__.py`:

```python
"""Declarative scene templates.

A template owns one *kind* of explanation. It validates the model's arguments and
compiles them into a complete, flat Manim source file — flat on purpose, because
the model may have to read and repair that file on the next turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping


class SceneSpecError(ValueError):
    """The supplied arguments cannot be turned into a scene.

    Raised before any rendering happens, so a bad argument costs milliseconds
    instead of a ten-second Manim run.
    """


@dataclass(frozen=True)
class SceneTemplate:
    """One declarative tool's code generator."""

    name: str
    scene_class: str
    summary: str
    params: Mapping[str, str]
    build: Callable[..., str]
    _cache: dict = field(default_factory=dict, repr=False, compare=False)


def _load() -> dict[str, SceneTemplate]:
    from . import compare, diagram, equation, graph

    templates: list[SceneTemplate] = []
    for module in (equation, graph, diagram, compare):
        templates.append(
            SceneTemplate(
                name=module.NAME,
                scene_class=module.SCENE_CLASS,
                summary=module.SUMMARY,
                params=dict(module.PARAMS),
                build=module.build,
            )
        )
    return {template.name: template for template in templates}


_CACHE: dict[str, SceneTemplate] | None = None


def registry() -> dict[str, SceneTemplate]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load()
    return _CACHE


def build(template_name: str, **params) -> tuple[str, str]:
    """Compile a template into `(scene_class, source)`."""
    template = registry().get(template_name)
    if template is None:
        known = ", ".join(sorted(registry()))
        raise SceneSpecError(f"unknown template {template_name!r}; known templates: {known}")
    code = template.build(**params)
    return template.scene_class, code


def catalogue() -> list[dict]:
    """The machine-readable template list `style_guide` hands to the model."""
    return [
        {
            "name": template.name,
            "sceneClass": template.scene_class,
            "summary": template.summary,
            "params": dict(template.params),
        }
        for template in sorted(registry().values(), key=lambda item: item.name)
    ]
```

`manim-mcp/manim_mcp/scenes/equation.py`:

```python
"""Step-by-step LaTeX derivation — 3b1b's signature animation."""

from __future__ import annotations

import json
from typing import Sequence

from ..style import preamble
from . import SceneSpecError

NAME = "equation"
SCENE_CLASS = "EquationScene"
SUMMARY = "把一串 LaTeX 公式逐步变形，展示推导过程（2-6 步）"
PARAMS = {
    "title": "可选，顶部标题；中文会自动使用中文字体",
    "steps": "必填，2-6 个 LaTeX 字符串，每一步一个状态",
    "highlight": "可选，与 steps 等长的子串数组；每一步要高亮的 LaTeX 片段（必须是该步中真实存在的子串，否则静默不高亮）",
    "cjk_font": "可选，中文正文字体名；通常留空自动探测",
}

MIN_STEPS = 2
MAX_STEPS = 6

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

class EquationScene(Scene):
    def construct(self):
        steps = [
@@STEPS@@
        ]
        highlight = [
@@HIGHLIGHT@@
        ]
        HAS_TITLE = @@HAS_TITLE@@
        HAS_HIGHLIGHT = @@HAS_HIGHLIGHT@@

        expression = MathTex(steps[0])
        if HAS_HIGHLIGHT and highlight[0]:
            expression.set_color_by_tex(highlight[0], C_HIGHLIGHT)

        if HAS_TITLE:
            title = cn(@@TITLE@@, TITLE_SIZE, WHITE).to_edge(UP, buff=0.9)
            expression.next_to(title, DOWN, buff=0.7)
            self.play(Write(title), run_time=PLAY_RUN_TIME)

        self.play(Write(expression), run_time=PLAY_RUN_TIME)
        self.wait(TAIL_WAIT)

        for index in range(1, len(steps)):
            following = MathTex(steps[index])
            following.move_to(expression)
            if HAS_HIGHLIGHT and highlight[index]:
                following.set_color_by_tex(highlight[index], C_HIGHLIGHT)
            self.play(
                TransformMatchingTex(expression, following),
                run_time=PLAY_RUN_TIME * 1.2,
            )
            expression = following
            self.wait(TAIL_WAIT)

        if HAS_HIGHLIGHT and highlight[-1]:
            self.play(
                Indicate(expression, color=C_HIGHLIGHT, scale_factor=1.06),
                run_time=PLAY_RUN_TIME,
            )
'''


def _literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _arguments(**kwargs) -> tuple[str | None, Sequence[str], Sequence[str] | None, str | None]:
    steps = kwargs.get("steps")
    if steps is None:
        raise SceneSpecError("equation: 缺少必填参数 steps（2-6 个 LaTeX 字符串）")
    if isinstance(steps, str) or not isinstance(steps, (list, tuple)):
        raise SceneSpecError("equation: steps 必须是字符串数组，不能是单个字符串")
    if not (MIN_STEPS <= len(steps) <= MAX_STEPS):
        raise SceneSpecError(
            f"equation: steps 需要 {MIN_STEPS}-{MAX_STEPS} 步，收到 {len(steps)} 步"
        )
    for index, step in enumerate(steps):
        if not isinstance(step, str) or not step.strip():
            raise SceneSpecError(f"equation: steps[{index}] 必须是非空字符串")

    highlight = kwargs.get("highlight")
    if highlight is None:
        highlight = ["" for _ in steps]
    else:
        if isinstance(highlight, str) or not isinstance(highlight, (list, tuple)):
            raise SceneSpecError("equation: highlight 必须是字符串数组，与 steps 等长")
        if len(highlight) != len(steps):
            raise SceneSpecError(
                f"equation: highlight 长度 {len(highlight)} 与 steps 长度 {len(steps)} 不一致"
            )
        for index, item in enumerate(highlight):
            if not isinstance(item, str):
                raise SceneSpecError(f"equation: highlight[{index}] 必须是字符串")

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("equation: title 必须是字符串")

    return title, list(steps), list(highlight), kwargs.get("cjk_font")


def build(**kwargs) -> str:
    title, steps, highlight, cjk_font = _arguments(**kwargs)
    body = "\n".join(f"            {_literal(step)}," for step in steps)
    marks = "\n".join(f"            {_literal(mark)}," for mark in highlight)
    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(cjk_font))
        .replace("@@STEPS@@", body)
        .replace("@@HIGHLIGHT@@", marks)
        .replace("@@HAS_TITLE@@", "True" if title else "False")
        .replace("@@TITLE@@", _literal(title or ""))
        .replace("@@HAS_HIGHLIGHT@@", "True" if any(highlight) else "False")
    )
```

> `scenes/__init__.py` 在 Task 9 才引入 `compare/diagram/graph`，因此**本任务必须同时创建这三个模块的最小占位实现**，否则注册表加载会失败。占位版本如下（Task 10-12 再替换为完整实现）：

`manim-mcp/manim_mcp/scenes/graph.py` / `diagram.py` / `compare.py` 各写：

```python
"""Placeholder replaced in a later task."""

from . import SceneSpecError


def build(**kwargs) -> str:
    raise SceneSpecError("this template is not implemented yet")
```

其余常量按各自 Task 补齐：`graph.py` 用 `NAME="graph"`、`SCENE_CLASS="GraphScene"`；`diagram.py` 用 `NAME="diagram"`、`SCENE_CLASS="DiagramScene"`；`compare.py` 用 `NAME="compare"`、`SCENE_CLASS="CompareScene"`。三个文件都要提供非空 `SUMMARY` 与 `PARAMS = {}`，`tests/test_scenes_registry.py` 才能通过。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_scenes_registry.py tests/test_scene_equation.py -v`
Expected: PASS（19 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/scenes tests/test_scenes_registry.py tests/test_scene_equation.py
git commit -m "feat(manim-mcp): 模板注册表与 equation 模板"
```

---

## Task 10: `scenes/graph.py` — 函数图像模板

**Files:**
- Modify: `manim-mcp/manim_mcp/scenes/graph.py`
- Test: `tests/test_scene_graph.py`

- [ ] **Step 1: 写失败测试**

`tests/test_scene_graph.py`:

```python
"""Graphs are where expressions are evaluated, so injection safety matters."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("graph", **kwargs)


def test_minimal_plot_compiles():
    scene_class, code = build(expressions=["x**2"])
    assert scene_class == "GraphScene"
    ast.parse(code)
    assert "x**2" in code


def test_numpy_expression_keeps_its_module_reference():
    _, code = build(expressions=["np.sin(x)"])
    ast.parse(code)
    assert "import numpy as np" in code
    assert "np.sin(x)" in code


def test_expression_is_evaluated_not_inlined():
    """The expression travels as a string, so a stray quote cannot break codegen."""
    _, code = build(expressions=['x if x > 0 else "neg"'])
    ast.parse(code)
    assert 'x if x > 0 else \\"neg\\"' in code or 'x if x > 0 else "neg"' in code


def test_multiple_expressions_are_kept_in_order():
    _, code = build(expressions=["x", "x**2", "np.cos(x)"])
    ast.parse(code)
    assert code.index('"x"') < code.index('"x**2"') < code.index('"np.cos(x)"')


def test_more_than_three_expressions_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=["x", "x**2", "x**3", "x**4"])


def test_empty_expression_list_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=[])


def test_blank_expression_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=["x", "  "])


def test_expression_must_be_a_string():
    with pytest.raises(SceneSpecError):
        build(expressions=[42])


def test_missing_expressions_is_rejected():
    with pytest.raises(SceneSpecError):
        build()


def test_custom_x_range_is_emitted():
    _, code = build(expressions=["x"], x_range=[-2, 2, 1])
    ast.parse(code)
    assert "X_RANGE = [-2, 2, 1]" in code


def test_default_x_range_is_used_when_absent():
    _, code = build(expressions=["x"])
    assert "X_RANGE = [-4, 4, 1]" in code


def test_x_range_must_be_three_numbers():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], x_range=[0, 1])


def test_x_range_bounds_must_be_ordered():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], x_range=[4, -4, 1])


def test_x_range_step_must_be_positive():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], x_range=[0, 1, 0])


def test_highlight_point_adds_a_dot_and_a_tangent():
    _, code = build(expressions=["x**2"], highlight={"x": 1.0, "tangent": True})
    ast.parse(code)
    assert "HIGHLIGHT_X = 1.0" in code
    assert "SHOW_TANGENT = True" in code
    assert "get_secant_slope_group" in code


def test_highlight_area_uses_the_axis_fill_helper():
    _, code = build(expressions=["x**2"], highlight={"x": 1.0, "area": [0, 2]})
    ast.parse(code)
    assert "SHOW_AREA = True" in code
    assert "get_area" in code


def test_highlight_requires_x():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], highlight={"tangent": True})


def test_tangent_without_a_highlight_x_is_rejected():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], highlight={"tangent": True, "x": None})


def test_parameter_block_binds_the_symbol_through_eval():
    _, code = build(
        expressions=["a * np.sin(x)"],
        parameter={"symbol": "a", "from": 0.5, "to": 3.0},
    )
    ast.parse(code)
    assert 'PARAM_SYMBOL = "a"' in code
    assert "PARAM_FROM = 0.5" in code
    assert "PARAM_TO = 3.0" in code
    assert "eval(" in code
    assert "ValueTracker" in code


def test_parameter_symbol_must_be_a_python_identifier():
    with pytest.raises(SceneSpecError) as caught:
        build(expressions=["x"], parameter={"symbol": "a-b", "from": 0, "to": 1})
    assert "a-b" in str(caught.value)


def test_parameter_range_must_be_finite_numbers():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], parameter={"symbol": "a", "from": "0", "to": 1})


def test_parameter_from_and_to_must_differ():
    with pytest.raises(SceneSpecError):
        build(expressions=["x"], parameter={"symbol": "a", "from": 1, "to": 1})


def test_y_range_default_is_emitted():
    _, code = build(expressions=["x"])
    assert "Y_RANGE = [-3, 3, 1]" in code
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_scene_graph.py -v`
Expected: FAIL — `SceneSpecError: this template is not implemented yet`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/scenes/graph.py`:

```python
"""Function plots with optional tangent, area fill, and a live parameter.

Expressions travel as *strings* and are evaluated with an explicit namespace. That
keeps codegen safe (no quoting or escaping of model text into source) and makes the
animated-parameter case fall out for free: the tracker's value is simply rebound in
the namespace on every frame.
"""

from __future__ import annotations

import json
import re
from typing import Mapping, Sequence

from ..style import preamble
from . import SceneSpecError

NAME = "graph"
SCENE_CLASS = "GraphScene"
SUMMARY = "函数图像，可叠加切线、面积填充与参数滑动"
PARAMS = {
    "title": "可选，顶部标题",
    "expressions": "必填，1-3 个 Python 表达式字符串，变量是 x，可用 np.*",
    "x_range": "可选，[起, 止, 步长]，默认 [-4, 4, 1]",
    "y_range": "可选，[起, 止, 步长]，默认 [-3, 3, 1]",
    "highlight": "可选，{x: 数值, tangent: 布尔, area: [a, b]}；x 必填",
    "parameter": "可选，{symbol: 标识符, from: 数值, to: 数值}；表达式中出现该符号即可动态变化",
    "cjk_font": "可选，中文字体名",
}

DEFAULT_X_RANGE = (-4.0, 4.0, 1.0)
DEFAULT_Y_RANGE = (-3.0, 3.0, 1.0)
MAX_EXPRESSIONS = 3
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TEMPLATE = '''from manim import *
import numpy as np

@@PREAMBLE@@

X_RANGE = @@X_RANGE@@
Y_RANGE = @@Y_RANGE@@
EXPRESSIONS = [
@@EXPRESSIONS@@
]
HAS_TITLE = @@HAS_TITLE@@
HIGHLIGHT_X = @@HIGHLIGHT_X@@
SHOW_TANGENT = @@SHOW_TANGENT@@
SHOW_AREA = @@SHOW_AREA@@
AREA_RANGE = @@AREA_RANGE@@
HAS_PARAMETER = @@HAS_PARAMETER@@
PARAM_SYMBOL = @@PARAM_SYMBOL@@
PARAM_FROM = @@PARAM_FROM@@
PARAM_TO = @@PARAM_TO@@
PLOT_COLORS = [C_BLUE, C_GREEN, C_RED]


def evaluate(expression, x, bindings):
    namespace = {"np": np, "x": x}
    namespace.update(bindings)
    return eval(expression, {"__builtins__": {}}, namespace)


class GraphScene(Scene):
    def construct(self):
        axes = Axes(
            x_range=X_RANGE,
            y_range=Y_RANGE,
            x_length=9.5,
            y_length=5.0,
            axis_config={"color": C_GREY, "include_numbers": True, "font_size": 22},
            tips=False,
        )
        labels = axes.get_axis_labels(MathTex("x"), MathTex("y"))
        self.play(Create(axes), Write(labels), run_time=1.0)

        if HAS_TITLE:
            title = cn(@@TITLE@@, TITLE_SIZE, WHITE).to_edge(UP, buff=0.6)
            self.play(Write(title), run_time=0.8)

        if HAS_PARAMETER:
            tracker = ValueTracker(PARAM_FROM)
            graphs = [
                always_redraw(
                    lambda expression=expression, color=color: axes.plot(
                        lambda x: evaluate(
                            expression, x, {PARAM_SYMBOL: tracker.get_value()}
                        ),
                        x_range=[X_RANGE[0], X_RANGE[1]],
                        color=color,
                    )
                )
                for expression, color in zip(EXPRESSIONS, PLOT_COLORS)
            ]
            self.add(*graphs)
            self.play(
                tracker.animate.set_value(PARAM_TO),
                run_time=3.0,
                rate_func=linear,
            )
        else:
            graphs = [
                axes.plot(
                    lambda x, expression=expression: evaluate(expression, x, {}),
                    x_range=[X_RANGE[0], X_RANGE[1]],
                    color=color,
                )
                for expression, color in zip(EXPRESSIONS, PLOT_COLORS)
            ]
            for graph in graphs:
                self.play(Create(graph), run_time=1.2)
                self.wait(0.3)

        primary = graphs[0]
        if HIGHLIGHT_X is not None:
            point = Dot(
                axes.c2p(HIGHLIGHT_X, evaluate(EXPRESSIONS[0], HIGHLIGHT_X, {})),
                color=C_HIGHLIGHT,
            )
            self.play(FadeIn(point, scale=0.6), run_time=0.6)

            if SHOW_TANGENT:
                slope_group = axes.get_secant_slope_group(
                    x=HIGHLIGHT_X,
                    graph=primary,
                    dx=0.01,
                    dx_line_color=C_HIGHLIGHT,
                    dy_line_color=C_HIGHLIGHT,
                    secant_line_color=C_HIGHLIGHT,
                    secant_line_length=3.5,
                )
                self.play(Create(slope_group), run_time=1.0)

            if SHOW_AREA:
                area = axes.get_area(
                    primary,
                    x_range=[AREA_RANGE[0], AREA_RANGE[1]],
                    color=C_HIGHLIGHT,
                    opacity=0.35,
                )
                self.play(FadeIn(area), run_time=1.0)

        self.wait(TAIL_WAIT)
'''


def _literal(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _range(value, default, label: str) -> tuple[float, float, float]:
    if value is None:
        return default
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or len(value) != 3:
        raise SceneSpecError(f"graph: {label} 必须是 [起, 止, 步长] 三个数")
    numbers: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise SceneSpecError(f"graph: {label}[{index}] 必须是数字")
        numbers.append(float(item))
    start, stop, step = numbers
    if start >= stop:
        raise SceneSpecError(f"graph: {label} 的起始值必须小于终止值")
    if step <= 0:
        raise SceneSpecError(f"graph: {label} 的步长必须为正数")
    return start, stop, step


def _expressions(value) -> list[str]:
    if value is None:
        raise SceneSpecError("graph: 缺少必填参数 expressions（1-3 个表达式字符串）")
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise SceneSpecError("graph: expressions 必须是字符串数组")
    if not value:
        raise SceneSpecError("graph: expressions 至少需要一个表达式")
    if len(value) > MAX_EXPRESSIONS:
        raise SceneSpecError(
            f"graph: expressions 最多 {MAX_EXPRESSIONS} 条，收到 {len(value)} 条"
        )
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise SceneSpecError(f"graph: expressions[{index}] 必须是非空字符串")
    return [str(item) for item in value]


def _highlight(value) -> tuple[float | None, bool, bool, tuple[float, float] | None]:
    if value is None:
        return None, False, False, None
    if not isinstance(value, Mapping):
        raise SceneSpecError("graph: highlight 必须是对象 {x, tangent, area}")

    point = value.get("x")
    if point is None:
        raise SceneSpecError("graph: highlight 缺少必填的 x")
    if isinstance(point, bool) or not isinstance(point, (int, float)):
        raise SceneSpecError("graph: highlight.x 必须是数字")
    point = float(point)

    tangent = bool(value.get("tangent", False))
    area_raw = value.get("area")
    if area_raw is None or area_raw is False:
        return point, tangent, False, None
    if area_raw is True:
        return point, tangent, True, (point - 1.0, point + 1.0)
    if isinstance(area_raw, str) or not isinstance(area_raw, (list, tuple)) or len(area_raw) != 2:
        raise SceneSpecError("graph: highlight.area 必须是 [a, b] 或 true")
    left, right = area_raw
    for index, item in enumerate((left, right)):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise SceneSpecError(f"graph: highlight.area[{index}] 必须是数字")
    if float(left) >= float(right):
        raise SceneSpecError("graph: highlight.area 的起点必须小于终点")
    return point, tangent, True, (float(left), float(right))


def _parameter(value) -> tuple[str, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise SceneSpecError("graph: parameter 必须是对象 {symbol, from, to}")
    symbol = value.get("symbol")
    if not isinstance(symbol, str) or not IDENTIFIER_RE.match(symbol):
        raise SceneSpecError(
            f"graph: parameter.symbol 必须是合法的 Python 标识符，收到 {symbol!r}"
        )
    start = value.get("from")
    stop = value.get("to")
    for name, item in (("from", start), ("to", stop)):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise SceneSpecError(f"graph: parameter.{name} 必须是数字")
    if float(start) == float(stop):
        raise SceneSpecError("graph: parameter 的 from 与 to 不能相同，否则动画没有变化")
    return symbol, float(start), float(stop)


def build(**kwargs) -> str:
    expressions = _expressions(kwargs.get("expressions"))
    x_range = _range(kwargs.get("x_range"), DEFAULT_X_RANGE, "x_range")
    y_range = _range(kwargs.get("y_range"), DEFAULT_Y_RANGE, "y_range")
    point, tangent, area, area_range = _highlight(kwargs.get("highlight"))
    parameter = _parameter(kwargs.get("parameter"))

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("graph: title 必须是字符串")

    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(kwargs.get("cjk_font")))
        .replace("@@X_RANGE@@", _literal(list(x_range)))
        .replace("@@Y_RANGE@@", _literal(list(y_range)))
        .replace("@@EXPRESSIONS@@", "\n".join(f"    {_literal(e)}," for e in expressions))
        .replace("@@HAS_TITLE@@", "True" if title else "False")
        .replace("@@TITLE@@", _literal(title or ""))
        .replace("@@HIGHLIGHT_X@@", "None" if point is None else repr(point))
        .replace("@@SHOW_TANGENT@@", "True" if tangent else "False")
        .replace("@@SHOW_AREA@@", "True" if area else "False")
        .replace("@@AREA_RANGE@@", "None" if area_range is None else _literal(list(area_range)))
        .replace("@@HAS_PARAMETER@@", "True" if parameter else "False")
        .replace("@@PARAM_SYMBOL@@", _literal(parameter[0] if parameter else ""))
        .replace("@@PARAM_FROM@@", repr(parameter[1]) if parameter else "0.0")
        .replace("@@PARAM_TO@@", repr(parameter[2]) if parameter else "0.0")
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_scene_graph.py -v`
Expected: PASS（20 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/scenes/graph.py tests/test_scene_graph.py
git commit -m "feat(manim-mcp): graph 模板"
```

---

## Task 11: `scenes/diagram.py` — 流程与结构模板

**Files:**
- Modify: `manim-mcp/manim_mcp/scenes/diagram.py`
- Test: `tests/test_scene_diagram.py`

- [ ] **Step 1: 写失败测试**

`tests/test_scene_diagram.py`:

```python
"""Diagrams are node/edge graphs; validation must catch dangling references."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("diagram", **kwargs)


NODES = [
    {"id": "a", "label": "输入"},
    {"id": "b", "label": "处理"},
    {"id": "c", "label": "输出"},
]
EDGES = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]


def test_minimal_diagram_compiles():
    scene_class, code = build(nodes=NODES, edges=EDGES)
    assert scene_class == "DiagramScene"
    ast.parse(code)
    assert "输入" in code and "输出" in code


def test_node_order_is_preserved():
    _, code = build(nodes=NODES, edges=EDGES)
    assert code.index('"输入"') < code.index('"处理"') < code.index('"输出"')


def test_edge_referencing_an_unknown_node_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=NODES, edges=[{"from": "a", "to": "zzz"}])
    assert "zzz" in str(caught.value)


def test_duplicate_node_ids_are_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=[{"id": "a", "label": "x"}, {"id": "a", "label": "y"}], edges=[])
    assert "a" in str(caught.value)


def test_nodes_must_be_a_non_empty_list():
    with pytest.raises(SceneSpecError):
        build(nodes=[], edges=[])
    with pytest.raises(SceneSpecError):
        build(edges=[])


def test_node_needs_both_id_and_label():
    with pytest.raises(SceneSpecError):
        build(nodes=[{"id": "a"}], edges=[])
    with pytest.raises(SceneSpecError):
        build(nodes=[{"label": "x"}], edges=[])


def test_more_than_eight_nodes_is_rejected():
    many = [{"id": f"n{i}", "label": f"节点{i}"} for i in range(9)]
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=many, edges=[])
    assert "8" in str(caught.value)


def test_unknown_node_kind_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(nodes=[{"id": "a", "label": "x", "kind": "sparkle"}], edges=[])
    assert "sparkle" in str(caught.value)


def test_node_kind_defaults_to_process():
    _, code = build(nodes=[{"id": "a", "label": "x"}], edges=[])
    assert '("x", "process")' in code


def test_each_kind_maps_to_its_declared_colour():
    _, code = build(
        nodes=[
            {"id": "a", "label": "p", "kind": "process"},
            {"id": "b", "label": "d", "kind": "decision"},
            {"id": "c", "label": "t", "kind": "terminal"},
            {"id": "d", "label": "g", "kind": "data"},
        ],
        edges=[],
    )
    ast.parse(code)
    assert "KIND_COLORS" in code


def test_edge_label_is_optional_and_emitted():
    _, code = build(nodes=NODES, edges=[{"from": "a", "to": "b", "label": "是"}])
    ast.parse(code)
    assert "是" in code


def test_horizontal_layout_is_emitted():
    _, code = build(nodes=NODES, edges=EDGES, layout="horizontal")
    ast.parse(code)
    assert 'LAYOUT = "horizontal"' in code


def test_vertical_layout_is_the_default():
    _, code = build(nodes=NODES, edges=EDGES)
    assert 'LAYOUT = "vertical"' in code


def test_unknown_layout_is_rejected():
    with pytest.raises(SceneSpecError):
        build(nodes=NODES, edges=EDGES, layout="diagonal")


def test_edges_must_be_a_list():
    with pytest.raises(SceneSpecError):
        build(nodes=NODES, edges="a->b")


def test_blank_node_label_is_rejected():
    with pytest.raises(SceneSpecError):
        build(nodes=[{"id": "a", "label": "   "}], edges=[])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_scene_diagram.py -v`
Expected: FAIL — `SceneSpecError: this template is not implemented yet`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/scenes/diagram.py`:

```python
"""Boxes and arrows: the shape of a process, a pipeline, or a hierarchy."""

from __future__ import annotations

import json
from typing import Mapping, Sequence

from ..style import preamble
from . import SceneSpecError

NAME = "diagram"
SCENE_CLASS = "DiagramScene"
SUMMARY = "流程 / 架构 / 因果关系的框图，节点 + 箭头"
PARAMS = {
    "title": "可选，顶部标题",
    "nodes": "必填，1-8 个 {id, label, kind}；kind 取 process/decision/terminal/data（只影响配色）",
    "edges": "必填，{from, to, label?} 数组；from/to 必须是已声明的 id",
    "layout": "可选，vertical（默认）或 horizontal",
    "cjk_font": "可选，中文字体名",
}

MAX_NODES = 8
KINDS = ("process", "decision", "terminal", "data")
LAYOUTS = ("vertical", "horizontal")

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

LAYOUT = @@LAYOUT@@
TITLE = @@TITLE@@
KIND_COLORS = {
    "process": C_BLUE,
    "decision": C_HIGHLIGHT,
    "terminal": C_GREEN,
    "data": C_GREY,
}
NODE_SPECS = [
@@NODES@@
]
EDGE_SPECS = [
@@EDGES@@
]


class DiagramScene(Scene):
    def construct(self):
        boxes = VGroup()
        index_of = {}
        for position, (node_id, label, kind) in enumerate(NODE_SPECS):
            box = RoundedRectangle(
                corner_radius=0.14,
                width=max(2.6, 0.34 * len(label) + 0.9),
                height=0.95,
                color=KIND_COLORS[kind],
                fill_opacity=0.14,
                stroke_width=2.5,
            )
            caption = cn(label, NOTE_SIZE, WHITE)
            caption.move_to(box)
            boxes.add(VGroup(box, caption))
            index_of[node_id] = position

        if LAYOUT == "horizontal":
            boxes.arrange(RIGHT, buff=1.1)
        else:
            boxes.arrange(DOWN, buff=0.55)
        boxes.move_to(ORIGIN)

        if TITLE:
            title = cn(TITLE, TITLE_SIZE, WHITE).to_edge(UP, buff=0.6)
            boxes.scale_to_fit_height(min(boxes.height, 4.6))
            boxes.next_to(title, DOWN, buff=0.55)
            self.play(Write(title), run_time=0.8)

        arrows = VGroup()
        labels = VGroup()
        for source, target, edge_label in EDGE_SPECS:
            start_box = boxes[index_of[source]][0]
            end_box = boxes[index_of[target]][0]
            arrow = Arrow(
                start_box.get_center(),
                end_box.get_center(),
                buff=0.62,
                color=C_GREY,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.12,
            )
            arrows.add(arrow)
            if edge_label:
                tag = cn(edge_label, NOTE_SIZE - 6, C_HIGHLIGHT)
                tag.move_to(arrow.get_center() + RIGHT * 0.42)
                labels.add(tag)

        self.play(
            LaggedStart(
                *[FadeIn(box, shift=RIGHT * 0.25) for box in boxes],
                lag_ratio=0.22,
            ),
            run_time=1.4,
        )
        if arrows:
            self.play(
                LaggedStart(*[GrowArrow(arrow) for arrow in arrows], lag_ratio=0.22),
                run_time=1.2,
            )
        if labels:
            self.play(FadeIn(labels), run_time=0.5)
        self.wait(TAIL_WAIT)
'''


def _literal(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _nodes(value) -> list[tuple[str, str, str]]:
    if value is None:
        raise SceneSpecError("diagram: 缺少必填参数 nodes")
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise SceneSpecError("diagram: nodes 必须是数组")
    if not value:
        raise SceneSpecError("diagram: nodes 至少需要一个节点")
    if len(value) > MAX_NODES:
        raise SceneSpecError(f"diagram: nodes 最多 {MAX_NODES} 个，收到 {len(value)} 个")

    parsed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for index, node in enumerate(value):
        if not isinstance(node, Mapping):
            raise SceneSpecError(f"diagram: nodes[{index}] 必须是对象 {{id, label, kind}}")
        node_id = node.get("id")
        label = node.get("label")
        if not isinstance(node_id, str) or not node_id.strip():
            raise SceneSpecError(f"diagram: nodes[{index}] 缺少非空的 id")
        if not isinstance(label, str) or not label.strip():
            raise SceneSpecError(f"diagram: nodes[{index}] 缺少非空的 label")
        if node_id in seen:
            raise SceneSpecError(f"diagram: 节点 id {node_id!r} 重复")
        seen.add(node_id)
        kind = node.get("kind", "process")
        if kind not in KINDS:
            raise SceneSpecError(
                f"diagram: 节点 {node_id!r} 的 kind {kind!r} 无效，可选 {', '.join(KINDS)}"
            )
        parsed.append((node_id, str(label), str(kind)))
    return parsed


def _edges(value, node_ids: set[str]) -> list[tuple[str, str, str | None]]:
    if value is None:
        raise SceneSpecError("diagram: 缺少必填参数 edges（可以为空数组）")
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise SceneSpecError("diagram: edges 必须是数组")

    parsed: list[tuple[str, str, str | None]] = []
    for index, edge in enumerate(value):
        if not isinstance(edge, Mapping):
            raise SceneSpecError(f"diagram: edges[{index}] 必须是对象 {{from, to, label?}}")
        source = edge.get("from")
        target = edge.get("to")
        for name, node_id in (("from", source), ("to", target)):
            if not isinstance(node_id, str) or not node_id.strip():
                raise SceneSpecError(f"diagram: edges[{index}].{name} 必须是非空字符串")
            if node_id not in node_ids:
                raise SceneSpecError(
                    f"diagram: edges[{index}].{name} 指向未声明的节点 {node_id!r}"
                )
        label = edge.get("label")
        if label is not None and not isinstance(label, str):
            raise SceneSpecError(f"diagram: edges[{index}].label 必须是字符串")
        parsed.append((str(source), str(target), label))
    return parsed


def build(**kwargs) -> str:
    nodes = _nodes(kwargs.get("nodes"))
    node_ids = {node[0] for node in nodes}
    edges = _edges(kwargs.get("edges"), node_ids)

    layout = kwargs.get("layout", "vertical")
    if layout not in LAYOUTS:
        raise SceneSpecError(
            f"diagram: layout {layout!r} 无效，可选 {', '.join(LAYOUTS)}"
        )

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("diagram: title 必须是字符串")

    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(kwargs.get("cjk_font")))
        .replace("@@LAYOUT@@", _literal(layout))
        .replace("@@TITLE@@", _literal(title or ""))
        .replace(
            "@@NODES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in nodes),
        )
        .replace(
            "@@EDGES@@",
            "\n".join(f"    ({_literal(a)}, {_literal(b)}, {_literal(c)})," for a, b, c in edges),
        )
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_scene_diagram.py -v`
Expected: PASS（16 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/scenes/diagram.py tests/test_scene_diagram.py
git commit -m "feat(manim-mcp): diagram 模板"
```

---

## Task 12: `scenes/compare.py` — 左右对照模板

**Files:**
- Modify: `manim-mcp/manim_mcp/scenes/compare.py`
- Test: `tests/test_scene_compare.py`

- [ ] **Step 1: 写失败测试**

`tests/test_scene_compare.py`:

```python
"""Side-by-side comparison: the anti-pattern / pattern explainer."""

import ast

import pytest

from manim_mcp import scenes
from manim_mcp.scenes import SceneSpecError


def build(**kwargs):
    return scenes.build("compare", **kwargs)


LEFT = {"title": "错误做法", "items": ["先写实现", "再补测试"]}
RIGHT = {"title": "推荐做法", "items": ["先写测试", "再写实现"]}


def test_minimal_comparison_compiles():
    scene_class, code = build(left=LEFT, right=RIGHT)
    assert scene_class == "CompareScene"
    ast.parse(code)
    assert "错误做法" in code
    assert "推荐做法" in code


def test_items_keep_their_order():
    _, code = build(left=LEFT, right=RIGHT)
    assert code.index("先写实现") < code.index("再补测试")
    assert code.index("先写测试") < code.index("再写实现")


def test_side_must_be_an_object():
    with pytest.raises(SceneSpecError):
        build(left="nope", right=RIGHT)


def test_side_requires_a_title():
    with pytest.raises(SceneSpecError):
        build(left={"items": ["a"]}, right=RIGHT)


def test_side_requires_at_least_one_item():
    with pytest.raises(SceneSpecError):
        build(left={"title": "x", "items": []}, right=RIGHT)


def test_more_than_five_items_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(left={"title": "x", "items": [f"i{i}" for i in range(6)]}, right=RIGHT)
    assert "5" in str(caught.value)


def test_blank_item_is_rejected():
    with pytest.raises(SceneSpecError):
        build(left={"title": "x", "items": ["ok", "  "]}, right=RIGHT)


def test_missing_left_is_rejected():
    with pytest.raises(SceneSpecError):
        build(right=RIGHT)


def test_title_is_optional_but_emitted_when_present():
    _, with_title = build(left=LEFT, right=RIGHT, title="两种顺序")
    _, without_title = build(left=LEFT, right=RIGHT)
    assert 'TITLE = "两种顺序"' in with_title
    assert 'TITLE = ""' in without_title


def test_left_and_right_use_distinct_accent_colours():
    _, code = build(left=LEFT, right=RIGHT)
    ast.parse(code)
    assert "LEFT_COLOR = C_RED" in code
    assert "RIGHT_COLOR = C_GREEN" in code


def test_custom_colours_are_honoured():
    _, code = build(left=LEFT, right=RIGHT, left_color="blue", right_color="grey")
    assert "LEFT_COLOR = C_BLUE" in code
    assert "RIGHT_COLOR = C_GREY" in code


def test_unknown_colour_name_is_rejected():
    with pytest.raises(SceneSpecError) as caught:
        build(left=LEFT, right=RIGHT, left_color="chartreuse")
    assert "chartreuse" in str(caught.value)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_scene_compare.py -v`
Expected: FAIL — `SceneSpecError: this template is not implemented yet`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/scenes/compare.py`:

```python
"""Two columns, one contrast: the fastest way to make a difference legible."""

from __future__ import annotations

import json
from typing import Mapping

from ..style import preamble
from . import SceneSpecError

NAME = "compare"
SCENE_CLASS = "CompareScene"
SUMMARY = "左右对照，突出两种做法/两个概念的差异"
PARAMS = {
    "title": "可选，顶部标题",
    "left": "必填，{title, items}；items 为 1-5 条",
    "right": "必填，{title, items}；items 为 1-5 条",
    "left_color": "可选，red（默认）/ blue / green / highlight / grey",
    "right_color": "可选，green（默认）/ red / blue / highlight / grey",
    "cjk_font": "可选，中文字体名",
}

MAX_ITEMS = 5
COLORS = {
    "red": "C_RED",
    "blue": "C_BLUE",
    "green": "C_GREEN",
    "highlight": "C_HIGHLIGHT",
    "grey": "C_GREY",
}

_TEMPLATE = '''from manim import *

@@PREAMBLE@@

TITLE = @@TITLE@@
LEFT_COLOR = @@LEFT_COLOR@@
RIGHT_COLOR = @@RIGHT_COLOR@@
LEFT_SIDE = (
    @@LEFT_TITLE@@,
    [
@@LEFT_ITEMS@@
    ],
)
RIGHT_SIDE = (
    @@RIGHT_TITLE@@,
    [
@@RIGHT_ITEMS@@
    ],
)


class CompareScene(Scene):
    def build_card(self, heading, items, accent):
        title = cn(heading, BODY_SIZE, accent)
        rows = VGroup(*[cn(item, NOTE_SIZE, WHITE) for item in items])
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        body = VGroup(title, rows).arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        frame = RoundedRectangle(
            corner_radius=0.18,
            width=max(4.3, body.width + 1.2),
            height=max(3.0, body.height + 1.0),
            color=accent,
            fill_opacity=0.10,
            stroke_width=2.5,
        )
        body.move_to(frame.get_center())
        return VGroup(frame, body)

    def construct(self):
        left_card = self.build_card(LEFT_SIDE[0], LEFT_SIDE[1], LEFT_COLOR)
        right_card = self.build_card(RIGHT_SIDE[0], RIGHT_SIDE[1], RIGHT_COLOR)
        cards = VGroup(left_card, right_card).arrange(RIGHT, buff=0.9)

        if TITLE:
            heading = cn(TITLE, TITLE_SIZE, WHITE).to_edge(UP, buff=0.7)
            cards.next_to(heading, DOWN, buff=0.6)
            self.play(Write(heading), run_time=0.8)

        self.play(FadeIn(left_card, shift=RIGHT * 0.4), run_time=1.0)
        self.play(FadeIn(right_card, shift=LEFT * 0.4), run_time=1.0)
        self.wait(TAIL_WAIT)
'''


def _literal(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _side(value, name: str) -> tuple[str, list[str]]:
    if value is None:
        raise SceneSpecError(f"compare: 缺少必填参数 {name}")
    if not isinstance(value, Mapping):
        raise SceneSpecError(f"compare: {name} 必须是对象 {{title, items}}")
    title = value.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SceneSpecError(f"compare: {name}.title 必须是非空字符串")
    items = value.get("items")
    if isinstance(items, str) or not isinstance(items, (list, tuple)):
        raise SceneSpecError(f"compare: {name}.items 必须是字符串数组")
    if not items:
        raise SceneSpecError(f"compare: {name}.items 至少需要一条")
    if len(items) > MAX_ITEMS:
        raise SceneSpecError(
            f"compare: {name}.items 最多 {MAX_ITEMS} 条，收到 {len(items)} 条"
        )
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise SceneSpecError(f"compare: {name}.items[{index}] 必须是非空字符串")
    return str(title), [str(item) for item in items]


def _color(value, default: str, name: str) -> str:
    if value is None:
        return COLORS[default]
    if not isinstance(value, str) or value not in COLORS:
        raise SceneSpecError(
            f"compare: {name} {value!r} 无效，可选 {', '.join(sorted(COLORS))}"
        )
    return COLORS[value]


def build(**kwargs) -> str:
    left_title, left_items = _side(kwargs.get("left"), "left")
    right_title, right_items = _side(kwargs.get("right"), "right")
    left_color = _color(kwargs.get("left_color"), "red", "left_color")
    right_color = _color(kwargs.get("right_color"), "green", "right_color")

    title = kwargs.get("title")
    if title is not None and not isinstance(title, str):
        raise SceneSpecError("compare: title 必须是字符串")

    return (
        _TEMPLATE.replace("@@PREAMBLE@@", preamble(kwargs.get("cjk_font")))
        .replace("@@TITLE@@", _literal(title or ""))
        .replace("@@LEFT_COLOR@@", left_color)
        .replace("@@RIGHT_COLOR@@", right_color)
        .replace("@@LEFT_TITLE@@", _literal(left_title))
        .replace("@@RIGHT_TITLE@@", _literal(right_title))
        .replace(
            "@@LEFT_ITEMS@@",
            "\n".join(f"        {_literal(item)}," for item in left_items),
        )
        .replace(
            "@@RIGHT_ITEMS@@",
            "\n".join(f"        {_literal(item)}," for item in right_items),
        )
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_scene_compare.py -v`
Expected: PASS（12 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/scenes/compare.py tests/test_scene_compare.py
git commit -m "feat(manim-mcp): compare 模板"
```

---

## Task 13: `tools/envelope.py` — 统一信封与双内容块

**Files:**
- Create: `manim-mcp/manim_mcp/tools/envelope.py`
- Test: `tests/test_envelope.py`

- [ ] **Step 1: 写失败测试**

`tests/test_envelope.py`:

```python
"""One return shape for every tool, plus the image block the model actually sees."""

import base64
import json
from pathlib import Path

from mcp.types import ImageContent, TextContent

from manim_mcp.tools import envelope

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


def decode(blocks) -> dict:
    assert isinstance(blocks[0], TextContent)
    return json.loads(blocks[0].text)


def test_success_payload_carries_the_documented_keys():
    payload = envelope.success_payload(
        run_id="20260912-153012-a1b2",
        scene_name="EquationScene",
        assets={"mp4": r"D:\r\a.mp4", "preview": r"D:\r\a.gif", "poster": r"D:\r\a.png"},
        preview_markdown="![anim](/D:/r/a.gif)",
        duration_sec=10.4,
        render_seconds=9.8,
        preview_bytes=73421,
        quality="draft",
        warnings=["GIF 超过目标体积 8388608B，实际 9000000B"],
    )
    assert payload["ok"] is True
    assert payload["runId"] == "20260912-153012-a1b2"
    assert payload["sceneName"] == "EquationScene"
    assert payload["previewMarkdown"] == "![anim](/D:/r/a.gif)"
    assert payload["durationSec"] == 10.4
    assert payload["renderSeconds"] == 9.8
    assert payload["previewBytes"] == 73421
    assert payload["quality"] == "draft"
    assert payload["warnings"] == ["GIF 超过目标体积 8388608B，实际 9000000B"]


def test_success_payload_preview_markdown_can_be_absent():
    payload = envelope.success_payload(
        run_id="r", scene_name="S", assets={}, preview_markdown=None,
        duration_sec=1.0, render_seconds=1.0, preview_bytes=0,
        quality="draft", warnings=[],
    )
    assert payload["previewMarkdown"] is None


def test_failure_payload_nests_the_diagnostic():
    from manim_mcp.engine.diagnostics import Diagnostic

    payload = envelope.failure_payload(
        run_id="r",
        diagnostic=Diagnostic(
            stage="manim", type="NameError", message="name 'Circle' is not defined",
            line=9, source_line="        circle = Circle(radius=1)", hint="加 import",
            stderr_tail="tail",
        ),
        code_path=r"D:\r\scene.py",
    )
    assert payload["ok"] is False
    assert payload["stage"] == "manim"
    assert payload["error"]["type"] == "NameError"
    assert payload["error"]["line"] == 9
    assert payload["error"]["sourceLine"] == "        circle = Circle(radius=1)"
    assert payload["hint"] == "加 import"
    assert payload["codePath"] == r"D:\r\scene.py"
    assert payload["error"]["stderrTail"] == "tail"


def test_failure_payload_survives_a_bare_diagnostic():
    from manim_mcp.engine.diagnostics import Diagnostic

    payload = envelope.failure_payload(run_id="r", diagnostic=Diagnostic(stage="timeout"))
    assert payload["error"]["stage"] == "timeout"
    assert "type" not in payload["error"]
    assert payload["hint"] is None


def test_text_block_is_always_present_and_pretty_printed():
    payload = {"ok": True, "note": "中文"}
    blocks = envelope.content_blocks(payload)
    assert len(blocks) == 1
    assert isinstance(blocks[0], TextContent)
    assert "中文" in blocks[0].text
    assert "\n" in blocks[0].text


def test_image_block_is_appended_for_a_gif(tmp_path: Path):
    preview = tmp_path / "a.gif"
    preview.write_bytes(PNG)
    blocks = envelope.content_blocks({"ok": True}, preview, "gif")
    assert [type(block) for block in blocks] == [TextContent, ImageContent]
    assert blocks[1].mimeType == "image/gif"
    assert base64.b64decode(blocks[1].data) == PNG


def test_image_block_carries_the_webp_mime(tmp_path: Path):
    preview = tmp_path / "a.webp"
    preview.write_bytes(PNG)
    blocks = envelope.content_blocks({"ok": True}, preview, "webp")
    assert blocks[1].mimeType == "image/webp"


def test_missing_preview_file_yields_text_only(tmp_path: Path):
    blocks = envelope.content_blocks({"ok": True}, tmp_path / "absent.gif", "gif")
    assert len(blocks) == 1


def test_unknown_preview_kind_yields_text_only(tmp_path: Path):
    preview = tmp_path / "a.bmp"
    preview.write_bytes(PNG)
    blocks = envelope.content_blocks({"ok": True}, preview, "bmp")
    assert len(blocks) == 1


def test_no_preview_yields_text_only():
    assert len(envelope.content_blocks({"ok": True}, None, None)) == 1


def test_preview_markdown_helper_uses_the_slash_drive_form():
    assert envelope.preview_markdown(r"D:\myprogram\dshplugin\renders\r1\out\S.gif") == (
        "![anim](/D:/myprogram/dshplugin/renders/r1/out/S.gif)"
    )


def test_preview_markdown_rejects_a_path_with_markdown_breaking_characters():
    assert envelope.preview_markdown(r"D:\my (dir)\S.gif") is None
    assert envelope.preview_markdown(r"D:\我的目录\S.gif") is None


def test_preview_markdown_handles_a_posix_path():
    assert envelope.preview_markdown("/home/u/renders/r1/out/S.gif") == (
        "![anim](/home/u/renders/r1/out/S.gif)"
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_envelope.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.tools.envelope'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/tools/envelope.py`:

```python
"""One return shape for every tool.

The text block is what the model reads and can act on; the image block is what the
user sees. Both come from here so no tool can forget one of them, and so the
Markdown fallback path is generated in exactly one place.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from mcp.types import ImageContent, TextContent

from ..engine.diagnostics import Diagnostic
from ..engine.postprocess import MIME_BY_KIND

MARKDOWN_ALT = "anim"
# Markdown image destinations break on whitespace, parentheses, and non-ASCII.
UNSAFE_MARKDOWN_RE = re.compile(r"[\s()<>\"'\u4e00-\u9fff]")
# `D:/...` or `C:/...` — the form a Windows absolute path takes after slash
# normalisation, and the form Node's win32 `normalize` resolves back correctly
# once a single leading slash is prepended.
DRIVE_RE = re.compile(r"^[A-Za-z]:/")

SUPPORTED_IMAGE_MIMES = frozenset(MIME_BY_KIND.values())


def preview_markdown(path: str | Path) -> str | None:
    """The `/D:/...` Markdown image reference the DSH web UI rewrites to `/api/file`.

    Returns None when the path cannot survive Markdown, which is why run ids and
    file names are restricted to ASCII without spaces or brackets.
    """
    text = str(path)
    if not text or UNSAFE_MARKDOWN_RE.search(text):
        return None

    normalized = text.replace("\\", "/")
    if normalized.startswith("//"):
        return None
    if DRIVE_RE.match(normalized):
        normalized = "/" + normalized
    elif not normalized.startswith("/"):
        return None
    return f"![{MARKDOWN_ALT}]({normalized})"


def success_payload(
    *,
    run_id: str,
    scene_name: str,
    assets: dict,
    preview_markdown: str | None,
    duration_sec: float,
    render_seconds: float,
    preview_bytes: int,
    quality: str,
    warnings: list[str],
) -> dict:
    return {
        "ok": True,
        "runId": run_id,
        "sceneName": scene_name,
        "assets": assets,
        "previewMarkdown": preview_markdown,
        "durationSec": round(float(duration_sec), 2),
        "renderSeconds": round(float(render_seconds), 2),
        "previewBytes": int(preview_bytes),
        "quality": quality,
        "warnings": list(warnings),
    }


def failure_payload(
    *,
    run_id: str,
    diagnostic: Diagnostic,
    code_path: str | Path | None = None,
    warnings: list[str] | None = None,
) -> dict:
    payload: dict = {
        "ok": False,
        "runId": run_id,
        "stage": diagnostic.stage,
        "error": diagnostic.as_dict(),
        "hint": diagnostic.hint,
    }
    if code_path is not None:
        payload["codePath"] = str(code_path)
    if warnings:
        payload["warnings"] = list(warnings)
    return payload


def plain_payload(**fields) -> dict:
    """For tools that produce data rather than an artifact (`check`, `runs`, ...)."""
    return {"ok": bool(fields.pop("ok", True)), **fields}


def content_blocks(
    payload: dict,
    preview_path: Path | None = None,
    preview_kind: str | None = None,
) -> list[TextContent | ImageContent]:
    """Text envelope first, then the preview image when one is available."""
    blocks: list[TextContent | ImageContent] = [
        TextContent(
            type="text",
            text=json.dumps(payload, ensure_ascii=False, indent=2),
        )
    ]

    if preview_path is None or preview_kind is None:
        return blocks
    mime = MIME_BY_KIND.get(preview_kind)
    if mime is None or mime not in SUPPORTED_IMAGE_MIMES:
        return blocks
    try:
        data = Path(preview_path).read_bytes()
    except OSError:
        return blocks

    blocks.append(
        ImageContent(
            type="image",
            data=base64.b64encode(data).decode("ascii"),
            mimeType=mime,
        )
    )
    return blocks
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_envelope.py -v`
Expected: PASS（14 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/tools/envelope.py tests/test_envelope.py
git commit -m "feat(manim-mcp): 统一信封与双内容块"
```

---

## Task 14: `tools/check.py` 与 `tools/style_guide.py`

**Files:**
- Create: `manim-mcp/manim_mcp/tools/check.py`
- Create: `manim-mcp/manim_mcp/tools/style_guide.py`
- Test: `tests/test_tool_check.py`
- Test: `tests/test_tool_style_guide.py`

- [ ] **Step 1: 写失败测试**

`tests/test_tool_check.py`:

```python
"""check exists to make the cheap mistakes cheap, before a 10-second render."""

from manim_mcp.tools import check

GOOD = '''from manim import *


class Demo(Scene):
    def construct(self):
        self.play(Write(Text("hi")))
'''


def test_good_code_passes_with_the_scene_class_listed():
    result = check.check_code(GOOD)
    assert result["ok"] is True
    assert result["issues"] == []
    assert result["sceneClasses"] == ["Demo"]


def test_syntax_error_reports_the_line():
    result = check.check_code("from manim import *\nclass X(Scene)\n    pass\n")
    assert result["ok"] is False
    assert any("第 2 行" in issue for issue in result["issues"])


def test_missing_manim_import_is_reported():
    result = check.check_code("class Demo(Scene):\n    pass\n")
    assert result["ok"] is False
    assert any("from manim import *" in issue for issue in result["issues"])


def test_missing_scene_subclass_is_reported():
    result = check.check_code("from manim import *\n\nx = 1\n")
    assert result["ok"] is False
    assert any("Scene" in issue for issue in result["issues"])


def test_scene_without_construct_is_reported():
    result = check.check_code("from manim import *\n\n\nclass Demo(Scene):\n    pass\n")
    assert result["ok"] is False
    assert any("construct" in issue for issue in result["issues"])


def test_multiple_scene_classes_are_all_listed():
    code = (
        "from manim import *\n\n"
        "class A(Scene):\n    def construct(self):\n        pass\n\n"
        "class B(Scene):\n    def construct(self):\n        pass\n"
    )
    assert check.check_code(code)["sceneClasses"] == ["A", "B"]


def test_qualified_scene_base_is_recognised():
    code = (
        "import manim\n\n"
        "class Demo(manim.Scene):\n    def construct(self):\n        pass\n"
    )
    result = check.check_code(code)
    assert result["ok"] is True
    assert result["sceneClasses"] == ["Demo"]


def test_empty_code_is_reported():
    result = check.check_code("")
    assert result["ok"] is False
    assert any("空" in issue for issue in result["issues"])


def test_non_string_code_is_reported():
    result = check.check_code(None)
    assert result["ok"] is False


def test_suggested_scene_is_the_first_class():
    result = check.check_code(GOOD)
    assert result["suggestedScene"] == "Demo"
```

`tests/test_tool_style_guide.py`:

```python
"""The model needs exact constants at write time, not a narrative."""

import ast

from manim_mcp.tools import style_guide


def test_payload_reports_the_local_cjk_font():
    payload = style_guide.style_guide_payload(cjk_font="SimHei", fonts=["SimHei", "Arial"])
    assert payload["ok"] is True
    assert payload["cjkFont"] == "SimHei"


def test_payload_warns_when_no_cjk_font_exists():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=["Arial"])
    assert payload["cjkFont"] is None
    assert any("中文" in note for note in payload["warnings"])


def test_palette_matches_the_style_module():
    from manim_mcp import style

    payload = style_guide.style_guide_payload(cjk_font=None, fonts=[])
    assert payload["palette"]["background"] == style.BACKGROUND
    assert payload["palette"]["highlight"] == style.HIGHLIGHT


def test_templates_are_listed_with_their_params():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=[])
    names = {row["name"] for row in payload["templates"]}
    assert names == {"equation", "graph", "diagram", "compare"}
    equation = [row for row in payload["templates"] if row["name"] == "equation"][0]
    assert "steps" in equation["params"]


def test_skeleton_is_valid_python_and_uses_the_cjk_helper():
    payload = style_guide.style_guide_payload(cjk_font="SimHei", fonts=["SimHei"])
    ast.parse(payload["skeleton"])
    assert "cn(" in payload["skeleton"]
    assert "from manim import *" in payload["skeleton"]


def test_skeleton_embeds_the_preamble_so_it_is_paste_ready():
    payload = style_guide.style_guide_payload(cjk_font="SimHei", fonts=["SimHei"])
    assert 'FONT_CJK = "SimHei"' in payload["skeleton"]
    assert "C_BLUE =" in payload["skeleton"]
    assert "TAIL_WAIT = 0.5" in payload["skeleton"]


def test_skeleton_without_a_font_still_compiles():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=["Arial"])
    compile(payload["skeleton"], "<skeleton>", "exec")
    assert "FONT_CJK = None" in payload["skeleton"]


def test_api_notes_mention_the_known_traps():
    payload = style_guide.style_guide_payload(cjk_font=None, fonts=[])
    blob = "\n".join(payload["apiNotes"])
    assert ".animate" in blob
    assert "MathTex" in blob
    assert "run_time" in blob
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_tool_check.py tests/test_tool_style_guide.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.tools.check'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/tools/check.py`:

```python
"""Static pre-flight: reject what Manim would reject, in a tenth of a second."""

from __future__ import annotations

import ast

from . import envelope

IMPORT_HINT = "from manim import *"


def _scene_classes(tree: ast.Module) -> list[ast.ClassDef]:
    found: list[ast.ClassDef] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            if name == "Scene":
                found.append(node)
                break
    return found


def check_code(code: str) -> dict:
    """Report whether `code` is plausibly renderable, without running Manim."""
    if not isinstance(code, str) or not code.strip():
        return envelope.plain_payload(
            ok=False, issues=["code 为空：需要一段完整的 Manim 场景代码"], sceneClasses=[]
        )

    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return envelope.plain_payload(
            ok=False,
            issues=[f"语法错误：第 {error.lineno} 行 {error.msg}"],
            sceneClasses=[],
        )

    issues: list[str] = []
    classes = _scene_classes(tree)

    if IMPORT_HINT not in code:
        issues.append(f"缺少 `{IMPORT_HINT}`，Manim 的图形类会全部未定义")

    if not classes:
        issues.append("没有找到继承自 `Scene` 的类，Manim 无从渲染")
    else:
        for node in classes:
            if not any(
                isinstance(item, ast.FunctionDef) and item.name == "construct"
                for item in node.body
            ):
                issues.append(f"场景类 `{node.name}` 缺少 `construct` 方法")

    return envelope.plain_payload(
        ok=not issues,
        issues=issues,
        sceneClasses=[node.name for node in classes],
        suggestedScene=classes[0].name if classes else None,
        lineCount=len(code.splitlines()),
    )
```

`manim-mcp/manim_mcp/tools/style_guide.py`:

```python
"""The machine-precise half of the style contract.

The narrative half ("when to animate at all") lives in the Skill, which is only
loaded when it is relevant. This payload is what the model needs *while writing
code*: the exact palette, the font names that exist on this machine, the API traps
worth avoiding, and one skeleton it can adapt.
"""

from __future__ import annotations

from typing import Iterable

from .. import scenes, style
from . import envelope

API_NOTES = [
    "每个动画只讲一个想法；总时长控制在 8-20 秒。",
    "`self.play(...)` 的 `run_time` 默认 1.0 秒；收尾用 `self.wait(0.5)` 留出阅读时间。",
    "`.animate` 只能写成 `self.play(mob.animate.shift(...))`，不要先赋值再调用别的方法。",
    "数学内容用 `MathTex`；`Tex` 是文本模式，公式里的下划线与分数会报错。",
    "公式字符串请用原始字符串 `r\"...\"`，否则反斜杠会被 Python 吃掉。",
    "中文必须走 `cn()` 或用 `Text(..., font=FONT_CJK)`，否则会渲染成方框。",
    "图形默认按 `config.background_color` 反衬，直接用 `WHITE` 作正文颜色。",
    "避免自定义类与复杂继承：这段代码之后可能由模型自己读回来修改。",
]

SKELETON_BODY = '''

class Demo(Scene):
    def construct(self):
        heading = cn("核心结论", TITLE_SIZE, WHITE).to_edge(UP, buff=0.8)
        formula = MathTex(r"e^{i\\pi} + 1 = 0")
        formula.next_to(heading, DOWN, buff=0.8)
        ring = Circle(radius=1.1, color=C_BLUE).next_to(formula, DOWN, buff=0.7)

        self.play(Write(heading), run_time=PLAY_RUN_TIME)
        self.play(FadeIn(formula, shift=UP * 0.4), run_time=PLAY_RUN_TIME)
        self.play(Create(ring), run_time=PLAY_RUN_TIME)
        self.wait(TAIL_WAIT)
'''


def skeleton(cjk_font: str | None) -> str:
    """A paste-ready file: the preamble is embedded, so `cn` and the palette exist.

    Handing over a bare body would make the model paste code that dies with
    `NameError: name 'cn' is not defined`, so the guide ships the whole file.
    """
    from .. import style as style_mod

    return (
        "from manim import *\n\n"
        + style_mod.preamble(cjk_font)
        + SKELETON_BODY
    )


def style_guide_payload(
    cjk_font: str | None, fonts: Iterable[str] | None = None
) -> dict:
    facts = style.style_guide_facts(cjk_font, fonts)
    warnings: list[str] = []
    if cjk_font is None:
        warnings.append(
            "本机没有探测到可用的中文字体，中文可能显示为方框；"
            "请改用英文标签，或安装 Microsoft YaHei / SimHei。"
        )

    return envelope.plain_payload(
        palette=facts["palette"],
        typography=facts["typography"],
        pacing=facts["pacing"],
        cjkFont=cjk_font,
        availableCjkFonts=facts["availableCjkFonts"],
        apiNotes=list(API_NOTES),
        templates=scenes.catalogue(),
        skeleton=skeleton(cjk_font),
        warnings=warnings,
    )
```

> 骨架自带 `preamble()`，所以 `cn`、`C_BLUE`、`TITLE_SIZE`、`PLAY_RUN_TIME`、`TAIL_WAIT` 都有定义——模型可以直接把它交给 `render`，不需要自己补任何东西。测试里对骨架的 `ast.parse` 与 `"FONT_CJK" in skeleton` 两条断言就是钉住这一点。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_tool_check.py tests/test_tool_style_guide.py -v`
Expected: PASS（16 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/tools/check.py manim-mcp/manim_mcp/tools/style_guide.py tests/test_tool_check.py tests/test_tool_style_guide.py
git commit -m "feat(manim-mcp): check 与 style_guide 工具"
```

---

## Task 15: `tools/runs.py` — 历史查询

**Files:**
- Create: `manim-mcp/manim_mcp/tools/runs.py`
- Test: `tests/test_tool_runs.py`

- [ ] **Step 1: 写失败测试**

`tests/test_tool_runs.py`:

```python
"""`runs` exists so "改一下刚才那个动画" does not need the whole scene in context."""

from pathlib import Path

from manim_mcp.engine import index, workspace
from manim_mcp.tools import runs


def seed(tmp_path: Path, run_id: str, created: str, code: str = "from manim import *\n") -> None:
    paths = workspace.prepare_run(tmp_path, run_id)
    workspace.write_scene(paths, code)
    workspace.write_meta(
        paths,
        {
            "runId": run_id,
            "tool": "equation",
            "title": "欧拉恒等式",
            "status": "ok",
            "createdAt": created,
            "assets": {
                "preview": f"/tmp/{run_id}/out/S.gif",
                "previewKind": "gif",
                "mp4": f"/tmp/{run_id}/out/S.mp4",
            },
            "previewUrlPath": f"/tmp/{run_id}/out/S.gif",
        },
    )
    index.upsert_run(tmp_path, workspace.read_meta(paths))


def test_list_returns_newest_first_with_summaries(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    seed(tmp_path, "20260912-120000-0002", "2026-09-12T12:00:00+08:00")

    payload = runs.list_runs(tmp_path)
    assert payload["ok"] is True
    assert [row["runId"] for row in payload["runs"]] == [
        "20260912-120000-0002",
        "20260912-100000-0001",
    ]
    assert payload["runs"][0]["title"] == "欧拉恒等式"


def test_list_omits_the_scene_source(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00", "# secret\n")
    assert "source" not in runs.list_runs(tmp_path)["runs"][0]


def test_list_rebuilds_when_the_index_is_missing(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    index.index_path(tmp_path).unlink()
    payload = runs.list_runs(tmp_path)
    assert [row["runId"] for row in payload["runs"]] == ["20260912-100000-0001"]


def test_list_honours_the_limit(tmp_path: Path):
    for offset in range(5):
        seed(
            tmp_path,
            f"20260912-1{offset}0000-000{offset}",
            f"2026-09-12T1{offset}:00:00+08:00",
        )
    assert len(runs.list_runs(tmp_path, limit=2)["runs"]) == 2


def test_list_rejects_a_non_positive_limit(tmp_path: Path):
    payload = runs.list_runs(tmp_path, limit=0)
    assert payload["ok"] is False
    assert any("limit" in issue for issue in payload["issues"])


def test_list_on_an_empty_root_succeeds_with_no_runs(tmp_path: Path):
    payload = runs.list_runs(tmp_path)
    assert payload["ok"] is True
    assert payload["runs"] == []


def test_get_returns_the_full_source(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00", "# hello\nx=1\n")
    payload = runs.get_run(tmp_path, "20260912-100000-0001")
    assert payload["ok"] is True
    assert payload["source"] == "# hello\nx=1\n"
    assert payload["runId"] == "20260912-100000-0001"


def test_get_rejects_an_unknown_run(tmp_path: Path):
    payload = runs.get_run(tmp_path, "20260912-100000-0001")
    assert payload["ok"] is False
    assert any("不存在" in issue for issue in payload["issues"])


def test_get_rejects_a_malformed_run_id(tmp_path: Path):
    payload = runs.get_run(tmp_path, "../escape")
    assert payload["ok"] is False


def test_get_reports_a_missing_scene_file(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    (tmp_path / "20260912-100000-0001" / "scene.py").unlink()
    payload = runs.get_run(tmp_path, "20260912-100000-0001")
    assert payload["ok"] is False


def test_dispatch_routes_both_actions(tmp_path: Path):
    seed(tmp_path, "20260912-100000-0001", "2026-09-12T10:00:00+08:00")
    assert runs.dispatch(tmp_path, "list")["ok"] is True
    assert runs.dispatch(tmp_path, "get", "20260912-100000-0001")["ok"] is True


def test_dispatch_rejects_an_unknown_action(tmp_path: Path):
    payload = runs.dispatch(tmp_path, "delete")
    assert payload["ok"] is False
    assert any("action" in issue for issue in payload["issues"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_tool_runs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.tools.runs'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/tools/runs.py`:

```python
"""History: what has been rendered, and the source behind any of it."""

from __future__ import annotations

from pathlib import Path

from ..engine import index, workspace
from . import envelope

DEFAULT_LIMIT = 20
SUMMARY_KEYS = (
    "runId", "tool", "sceneName", "title", "status", "quality",
    "createdAt", "durationSec", "renderSeconds", "assets", "previewUrlPath", "warnings",
)


def _summary(entry: dict) -> dict:
    return {key: entry[key] for key in SUMMARY_KEYS if key in entry}


def _entries(root: Path) -> list[dict]:
    """Prefer the index; rebuild from disk when it is absent or stale-empty."""
    data = index.load_index(root)
    if data["runs"]:
        return data["runs"]
    return index.rebuild_index(root)["runs"]


def list_runs(root: Path, limit: int = DEFAULT_LIMIT) -> dict:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return envelope.plain_payload(
            ok=False, issues=[f"limit 必须是正整数，收到 {limit!r}"], runs=[]
        )
    entries = _entries(root)
    return envelope.plain_payload(
        ok=True,
        count=len(entries),
        shown=min(limit, len(entries)),
        renderRoot=str(root),
        runs=[_summary(entry) for entry in entries[:limit]],
    )


def get_run(root: Path, run_id: str) -> dict:
    if not workspace.is_valid_run_id(run_id):
        return envelope.plain_payload(
            ok=False,
            issues=[f"runId {run_id!r} 格式非法，应为 YYYYMMDD-HHMMSS-xxxx"],
        )
    if not (root / run_id).is_dir():
        return envelope.plain_payload(ok=False, issues=[f"runId {run_id!r} 不存在"])

    paths = workspace.run_paths(root, run_id)
    try:
        source = workspace.read_scene(paths)
    except OSError:
        return envelope.plain_payload(ok=False, issues=[f"{run_id} 的 scene.py 已不存在"])

    return envelope.plain_payload(
        ok=True,
        runId=run_id,
        meta=workspace.read_meta(paths),
        scenePath=str(paths.scene),
        source=source,
    )


def dispatch(root: Path, action: str, run_id: str | None = None, limit: int = DEFAULT_LIMIT) -> dict:
    if action == "list":
        return list_runs(root, limit)
    if action == "get":
        if not run_id:
            return envelope.plain_payload(ok=False, issues=["action=get 需要 run_id"])
        return get_run(root, run_id)
    return envelope.plain_payload(
        ok=False, issues=[f"未知 action {action!r}，可选 list 或 get"]
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_tool_runs.py -v`
Expected: PASS（12 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/tools/runs.py tests/test_tool_runs.py
git commit -m "feat(manim-mcp): runs 历史查询"
```

---

## Task 16: `tools/pipeline.py` — 渲染编排

**Files:**
- Create: `manim-mcp/manim_mcp/tools/pipeline.py`
- Create: `tests/helpers.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 写共享 stub 与失败测试**

`tests/helpers.py`（被本任务与 Task 17 共用，避免重复定义）：

```python
"""Shared fakes: pipeline, declarative, and render tests all need them."""

from __future__ import annotations

import json
from pathlib import Path

from manim_mcp.config import Config
from manim_mcp.engine import render
from manim_mcp.engine.diagnostics import Diagnostic
from manim_mcp.engine.postprocess import Preview


def make_config(render_root: Path, **overrides) -> Config:
    base = dict(
        python=r"D:\py\python.exe",
        manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe",
        render_root=render_root,
        max_concurrency=1,
        timeout_sec=30.0,
        gif_target_bytes=1000,
        gif_max_bytes=2000,
        keep_runs=50,
        log_level="INFO",
    )
    base.update(overrides)
    return Config(**base)


def stub_render(ok: bool, *, diagnostic: Diagnostic | None = None, seconds: float = 3.0):
    """A render callable that fabricates an artifact instead of running Manim."""

    def fake(cfg, paths, scene_name, quality, **kwargs):
        if ok:
            artifact = paths.out / f"{scene_name}.mp4"
            artifact.write_bytes(b"mp4")
            return render.RenderResult(ok=True, mp4=artifact, seconds=seconds)
        return render.RenderResult(
            ok=False,
            mp4=None,
            seconds=seconds,
            diagnostic=diagnostic or Diagnostic(stage="manim", message="boom"),
        )

    return fake


def stub_preview(kind: str | None = "gif", size: int = 800):
    """A preview callable that fabricates one artifact of the requested kind."""

    def fake(ffmpeg, mp4, out_dir, basename, *, target_bytes, max_bytes, **kwargs):
        if kind is None:
            return Preview(
                path=None,
                kind=None,
                byte_size=0,
                warnings=("ffmpeg 不可用，未生成预览图",),
            )
        path = out_dir / f"{basename}.{kind}"
        path.write_bytes(b"x" * size)
        return Preview(path=path, kind=kind, byte_size=size)

    return fake


def text_of(blocks) -> dict:
    """The JSON payload from a tool's first (text) content block."""
    return json.loads(blocks[0].text)
```

`tests/test_pipeline.py`:

```python
"""The one place where a render, a preview, and an index entry come together."""

from pathlib import Path

from manim_mcp.engine import index, workspace
from manim_mcp.engine.diagnostics import Diagnostic
from manim_mcp.tools import pipeline
from tests.helpers import make_config, stub_preview, stub_render, text_of

SCENE = (
    "from manim import *\n\n\n"
    "class EquationScene(Scene):\n"
    "    def construct(self):\n"
    "        pass\n"
)


def run(tmp_path: Path, **kwargs):
    cfg = kwargs.pop("cfg", None) or make_config(tmp_path)
    defaults = dict(
        tool_name="equation",
        title="欧拉恒等式",
        quality="draft",
        args_summary={"steps": 3},
        code=SCENE,
        scene_class="EquationScene",
        render_fn=stub_render(True),
        preview_fn=stub_preview(),
        run_id="20260912-153012-a1b2",
    )
    defaults.update(kwargs)
    return pipeline.execute(cfg, **defaults)


def test_success_creates_the_run_tree_and_two_blocks(tmp_path: Path):
    blocks = run(tmp_path)
    assert [block.type for block in blocks] == ["text", "image"]
    payload = text_of(blocks)
    assert payload["ok"] is True
    assert payload["runId"] == "20260912-153012-a1b2"
    assert payload["sceneName"] == "EquationScene"
    assert Path(payload["assets"]["mp4"]).exists()
    assert Path(payload["assets"]["preview"]).exists()


def test_success_preview_markdown_round_trips(tmp_path: Path):
    payload = text_of(run(tmp_path))
    markdown = payload["previewMarkdown"]
    assert markdown.startswith("![anim](/")
    assert markdown.endswith(".gif)")


def test_success_writes_run_json_and_index_adds_the_entry(tmp_path: Path):
    payload = text_of(run(tmp_path))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    meta = workspace.read_meta(paths)
    assert meta["status"] == "ok"
    assert meta["tool"] == "equation"
    assert meta["title"] == "欧拉恒等式"
    assert meta["sceneName"] == "EquationScene"

    entries = index.load_index(tmp_path)["runs"]
    assert [entry["runId"] for entry in entries] == [payload["runId"]]
    assert entries[0]["previewUrlPath"].endswith(".gif")


def test_success_records_the_argument_summary_not_the_source(tmp_path: Path):
    payload = text_of(run(tmp_path))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"steps": 3}
    assert "source" not in meta


def test_scene_source_is_written_to_disk(tmp_path: Path):
    payload = text_of(run(tmp_path))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    assert "EquationScene" in workspace.read_scene(paths)


def test_failure_returns_one_text_block_and_records_the_failure(tmp_path: Path):
    diagnostic = Diagnostic(
        stage="manim", type="NameError", message="name 'X' is not defined", line=4, hint="加 import"
    )
    blocks = run(tmp_path, render_fn=stub_render(False, diagnostic=diagnostic))
    assert [block.type for block in blocks] == ["text"]
    payload = text_of(blocks)
    assert payload["ok"] is False
    assert payload["stage"] == "manim"
    assert payload["error"]["type"] == "NameError"
    assert payload["hint"] == "加 import"
    assert Path(payload["codePath"]).exists()


def test_failure_still_lands_in_the_index_so_the_gallery_can_explain_it(tmp_path: Path):
    blocks = run(tmp_path, render_fn=stub_render(False))
    run_id = text_of(blocks)["runId"]
    entries = index.load_index(tmp_path)["runs"]
    assert entries[0]["runId"] == run_id
    assert entries[0]["status"] == "failed"


def test_missing_preview_degrades_to_text_only_with_a_warning(tmp_path: Path):
    blocks = run(tmp_path, preview_fn=stub_preview(None))
    assert [block.type for block in blocks] == ["text"]
    payload = text_of(blocks)
    assert payload["ok"] is True
    assert payload["previewMarkdown"] is None
    assert any("ffmpeg" in note for note in payload["warnings"])


def test_preview_path_with_markdown_breaking_characters_is_not_advertised(tmp_path: Path):
    cfg = make_config(tmp_path / "my (dir)")
    blocks = run(tmp_path, cfg=cfg)
    assert text_of(blocks)["previewMarkdown"] is None


def test_pruning_runs_after_a_successful_render(tmp_path: Path):
    cfg = make_config(tmp_path, keep_runs=1)
    for run_id in ("20260912-100000-0001", "20260912-120000-0002"):
        workspace.prepare_run(tmp_path, run_id)
    payload = text_of(run(tmp_path, cfg=cfg, run_id="20260912-130000-0003"))
    assert payload["ok"] is True
    surviving = workspace.existing_run_ids(tmp_path)
    assert surviving == ["20260912-130000-0003"]


def test_pruning_also_drops_the_index_entries(tmp_path: Path):
    cfg = make_config(tmp_path, keep_runs=1)
    for run_id in ("20260912-100000-0001", "20260912-120000-0002"):
        workspace.prepare_run(tmp_path, run_id)
        index.upsert_run(tmp_path, {"runId": run_id, "createdAt": "2026-09-12T10:00:00+08:00"})
    run(tmp_path, cfg=cfg, run_id="20260912-130000-0003")
    ids = [entry["runId"] for entry in index.load_index(tmp_path)["runs"]]
    assert ids == ["20260912-130000-0003"]


def test_index_write_failure_does_not_fail_the_render(tmp_path: Path, monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(pipeline.index, "upsert_run", explode)
    payload = text_of(run(tmp_path))
    assert payload["ok"] is True
    assert any("索引" in note for note in payload["warnings"])


def test_webp_preview_is_advertised_with_its_own_extension(tmp_path: Path):
    payload = text_of(run(tmp_path, preview_fn=stub_preview("webp")))
    assert payload["previewMarkdown"].endswith(".webp)")
    assert payload["assets"]["preview"].endswith(".webp")


def test_poster_only_preview_points_markdown_at_the_png(tmp_path: Path):
    payload = text_of(run(tmp_path, preview_fn=stub_preview("png")))
    assert payload["previewMarkdown"].endswith(".png)")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.tools.pipeline'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/tools/pipeline.py`:

```python
"""The single side-effecting path: render, preview, record, report.

Both the declarative tools and the raw-code escape hatch end here, so the run
layout, the index entry, the warning policy, and the content blocks are identical
no matter which tool the model picked.

A render that succeeds is never reported as a failure just because a *secondary*
step (index write, pruning) went wrong; those become warnings instead.
"""

from __future__ import annotations

import datetime as _datetime
from pathlib import Path
from typing import Callable

from mcp.types import ImageContent, TextContent

from .. import config as config_mod
from ..engine import index, postprocess, render, workspace
from . import envelope


def _iso_now() -> str:
    return _datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _prune_and_reconcile(cfg: config_mod.Config, run_id: str) -> list[str]:
    """Retention, then drop the index entries of whatever was removed."""
    removed = workspace.prune_runs(cfg.render_root, cfg.keep_runs)
    for gone in removed:
        if gone != run_id:
            index.remove_run(cfg.render_root, gone)
    return removed


def execute(
    cfg: config_mod.Config,
    *,
    tool_name: str,
    code: str,
    scene_class: str,
    quality: str,
    title: str | None,
    args_summary: dict,
    run_id: str,
    render_fn: Callable | None = None,
    preview_fn: Callable | None = None,
) -> list[TextContent | ImageContent]:
    """Run one render end to end and return the tool's content blocks."""
    paths = workspace.prepare_run(cfg.render_root, run_id)
    workspace.write_scene(paths, code)

    do_render = render_fn or render.render_scene
    outcome = do_render(cfg, paths, scene_class, quality)

    warnings: list[str] = []

    if not outcome.ok or outcome.mp4 is None:
        diagnostic = outcome.diagnostic
        payload = envelope.failure_payload(
            run_id=run_id, diagnostic=diagnostic, code_path=paths.scene
        )
        _record(
            cfg,
            paths=paths,
            tool_name=tool_name,
            title=title,
            quality=quality,
            args_summary=args_summary,
            status="failed",
            assets={},
            warnings=warnings,
        )
        return envelope.content_blocks(payload)

    do_preview = preview_fn or postprocess.build_preview
    preview = do_preview(
        cfg.ffmpeg,
        outcome.mp4,
        paths.out,
        scene_class,
        target_bytes=cfg.gif_target_bytes,
        max_bytes=cfg.gif_max_bytes,
    )
    warnings.extend(preview.warnings)

    duration = 0.0
    if cfg.ffmpeg:
        duration = postprocess.probe_duration(cfg.ffmpeg, outcome.mp4)

    poster = paths.out / f"{scene_class}.png"
    assets: dict = {"mp4": str(outcome.mp4)}
    if preview.path is not None:
        assets["preview"] = str(preview.path)
        assets["previewKind"] = preview.kind
    if poster.exists():
        assets["poster"] = str(poster)

    markdown = (
        envelope.preview_markdown(preview.path) if preview.path is not None else None
    )
    if preview.path is not None and markdown is None:
        warnings.append(
            "预览产物路径含有 Markdown 无法安全表示的字符，已省略内嵌预览，"
            "请把 assets 里的路径直接告诉用户。"
        )

    payload = envelope.success_payload(
        run_id=run_id,
        scene_name=scene_class,
        assets=assets,
        preview_markdown=markdown,
        duration_sec=duration,
        render_seconds=outcome.seconds,
        preview_bytes=preview.byte_size,
        quality=quality,
        warnings=warnings,
    )

    extra = _record(
        cfg,
        paths=paths,
        tool_name=tool_name,
        title=title,
        quality=quality,
        args_summary=args_summary,
        status="ok",
        assets=assets,
        warnings=warnings,
    )
    if extra:
        payload["warnings"] = warnings + extra

    return envelope.content_blocks(payload, preview.path, preview.kind)


def _record(
    cfg: config_mod.Config,
    *,
    paths: workspace.RunPaths,
    tool_name: str,
    title: str | None,
    quality: str,
    args_summary: dict,
    status: str,
    assets: dict,
    warnings: list[str],
) -> list[str]:
    """Persist run metadata and the index entry. Never raises."""
    notes: list[str] = []
    preview_url = ""
    if assets.get("preview"):
        markdown = envelope.preview_markdown(assets["preview"])
        if markdown:
            preview_url = markdown.split("](", 1)[1].rstrip(")")

    meta = {
        "runId": paths.run_id,
        "tool": tool_name,
        "sceneName": "EquationScene",
        "title": title,
        "status": status,
        "quality": quality,
        "createdAt": _iso_now(),
        "assets": assets,
        "previewUrlPath": preview_url,
        "args": args_summary,
        "warnings": list(warnings),
    }

    try:
        workspace.write_meta(paths, meta)
        index.upsert_run(cfg.render_root, meta)
    except Exception as error:  # noqa: BLE001 - a bookkeeping fault must not lose the render
        notes.append(f"索引未更新（渲染结果仍然有效）：{type(error).__name__}: {error}")
        return notes

    try:
        _prune_and_reconcile(cfg, paths.run_id)
    except Exception as error:  # noqa: BLE001 - retention is best effort
        notes.append(f"清理旧 run 失败：{type(error).__name__}: {error}")
    return notes
```

> `_record` 里写死的 `"sceneName": "EquationScene"` 是个 bug——它必须来自调用方。**Step 3 请直接把 `scene_name` 作为 `_record` 的参数传进来**：

```python
def _record(cfg, *, paths, tool_name, scene_name, title, quality, args_summary,
            status, assets, warnings) -> list[str]:
    ...
    meta = {"runId": paths.run_id, "tool": tool_name, "sceneName": scene_name, ...}
```

并在两处调用点分别传 `scene_name=scene_class`（成功路径）与 `scene_name=scene_class`（失败路径）。对应地，测试 `test_success_writes_run_json_and_index_adds_the_entry` 只断言 `meta["tool"]`，不受影响。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS（14 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/tools/pipeline.py tests/helpers.py tests/test_pipeline.py
git commit -m "feat(manim-mcp): 渲染编排流水线"
```

---

## Task 17: `tools/declarative.py` 与 `tools/render.py`

**Files:**
- Create: `manim-mcp/manim_mcp/tools/declarative.py`
- Create: `manim-mcp/manim_mcp/tools/render.py`
- Test: `tests/test_tool_declarative.py`
- Test: `tests/test_tool_render.py`

- [ ] **Step 1: 写失败测试**

`tests/test_tool_declarative.py`:

```python
"""Declarative tools compile a template, then hand off to the pipeline."""

from pathlib import Path

from manim_mcp.engine import workspace
from manim_mcp.tools import declarative
from tests.helpers import make_config, stub_preview, stub_render, text_of


def invoke(tmp_path: Path, template: str, **params):
    return declarative.run_template(
        make_config(tmp_path),
        template,
        quality=params.pop("quality", "draft"),
        title=params.pop("title", None),
        params=params,
        render_fn=stub_render(True),
        preview_fn=stub_preview(),
    )


def test_equation_produces_a_render_and_an_image_block(tmp_path: Path):
    blocks = invoke(tmp_path, "equation", steps=[r"a=b", r"a=c"])
    assert [block.type for block in blocks] == ["text", "image"]
    assert text_of(blocks)["sceneName"] == "EquationScene"


def test_each_template_reports_its_own_scene_class(tmp_path: Path):
    cases = {
        "equation": dict(steps=[r"a", r"b"]),
        "graph": dict(expressions=["x**2"]),
        "diagram": dict(nodes=[{"id": "a", "label": "甲"}], edges=[]),
        "compare": dict(
            left={"title": "甲", "items": ["1"]}, right={"title": "乙", "items": ["2"]}
        ),
    }
    expected = {
        "equation": "EquationScene",
        "graph": "GraphScene",
        "diagram": "DiagramScene",
        "compare": "CompareScene",
    }
    for template, params in cases.items():
        payload = text_of(invoke(tmp_path, template, **params))
        assert payload["sceneName"] == expected[template]


def test_generated_source_reaches_disk(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "equation", steps=[r"a=b", r"a=c"]))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    source = workspace.read_scene(paths)
    assert "class EquationScene(Scene):" in source
    assert '"a=c"' in source


def test_recorded_tool_name_is_the_template_name(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "graph", expressions=["x"]))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["tool"] == "graph"


def test_argument_summary_records_shapes_not_the_payload(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "equation", steps=[r"a", r"b", r"c"]))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"steps": 3}


def test_invalid_arguments_fail_before_any_run_directory_is_created(tmp_path: Path):
    blocks = invoke(tmp_path, "equation", steps=[r"only-one"])
    payload = text_of(blocks)
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert workspace.existing_run_ids(tmp_path) == []


def test_invalid_arguments_do_not_reach_the_renderer(tmp_path: Path):
    calls = []

    def spy_render(*args, **kwargs):
        calls.append(args)
        return stub_render(True)(*args, **kwargs)

    declarative.run_template(
        make_config(tmp_path), "graph", quality="draft", title=None,
        params={"expressions": []}, render_fn=spy_render, preview_fn=stub_preview(),
    )
    assert calls == []


def test_unknown_template_is_a_validate_failure(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "hologram"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert "hologram" in payload["error"]["message"]


def test_diagram_argument_summary_counts_nodes_and_edges(tmp_path: Path):
    payload = text_of(
        invoke(
            tmp_path,
            "diagram",
            nodes=[{"id": "a", "label": "甲"}, {"id": "b", "label": "乙"}],
            edges=[{"from": "a", "to": "b"}],
        )
    )
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"nodes": 2, "edges": 1}
```

`tests/test_tool_render.py`:

```python
"""The escape hatch: raw Manim code, with the same bookkeeping as any template."""

from pathlib import Path

from manim_mcp.engine import workspace
from manim_mcp.tools import render as render_tool
from tests.helpers import make_config, stub_preview, stub_render, text_of

GOOD = '''from manim import *


class Custom(Scene):
    def construct(self):
        self.play(Write(Text("hi")))
'''


def invoke(tmp_path: Path, code: str, scene_name=None, quality="draft"):
    return render_tool.run_code(
        make_config(tmp_path),
        code=code,
        scene_name=scene_name,
        quality=quality,
        render_fn=stub_render(True),
        preview_fn=stub_preview(),
    )


def test_valid_code_renders_and_infers_the_scene_class(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    assert payload["ok"] is True
    assert payload["sceneName"] == "Custom"


def test_explicit_scene_name_is_honoured(tmp_path: Path):
    code = GOOD + "\n\nclass Second(Scene):\n    def construct(self):\n        pass\n"
    payload = text_of(invoke(tmp_path, code, scene_name="Second"))
    assert payload["sceneName"] == "Second"


def test_unknown_scene_name_is_a_validate_failure(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD, scene_name="Absent"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert workspace.existing_run_ids(tmp_path) == []


def test_syntactically_broken_code_never_reaches_the_renderer(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "from manim import *\nclass X(Scene)\n    pass\n"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"
    assert workspace.existing_run_ids(tmp_path) == []


def test_missing_construct_never_reaches_the_renderer(tmp_path: Path):
    payload = text_of(invoke(tmp_path, "from manim import *\n\nclass X(Scene):\n    pass\n"))
    assert payload["ok"] is False
    assert payload["stage"] == "validate"


def test_recorded_tool_name_is_render(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["tool"] == "render"


def test_argument_summary_records_the_line_count_not_the_source(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    meta = workspace.read_meta(workspace.run_paths(tmp_path, payload["runId"]))
    assert meta["args"] == {"lines": len(GOOD.splitlines())}
    assert "source" not in meta


def test_the_model_source_is_written_verbatim(tmp_path: Path):
    payload = text_of(invoke(tmp_path, GOOD))
    paths = workspace.run_paths(tmp_path, payload["runId"])
    assert workspace.read_scene(paths) == GOOD
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_tool_declarative.py tests/test_tool_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.tools.declarative'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/tools/declarative.py`:

```python
"""The four declarative tools, plus the validation gate they share.

Validation runs before the run directory exists, so a malformed argument costs
nothing and leaves no debris in the gallery.
"""

from __future__ import annotations

from typing import Callable

from mcp.types import ImageContent, TextContent

from .. import config as config_mod
from .. import scenes
from ..engine import diagnostics, workspace
from . import envelope, pipeline

SUMMARY_BUILDERS: dict[str, Callable[[dict], dict]] = {
    "equation": lambda params: {"steps": len(params.get("steps") or [])},
    "graph": lambda params: {
        "expressions": len(params.get("expressions") or []),
        "parameter": bool(params.get("parameter")),
    },
    "diagram": lambda params: {
        "nodes": len(params.get("nodes") or []),
        "edges": len(params.get("edges") or []),
    },
    "compare": lambda params: {
        "leftItems": len((params.get("left") or {}).get("items") or []),
        "rightItems": len((params.get("right") or {}).get("items") or []),
    },
}


def run_template(
    cfg: config_mod.Config,
    template_name: str,
    *,
    quality: str,
    title: str | None,
    params: dict,
    render_fn: Callable | None = None,
    preview_fn: Callable | None = None,
) -> list[TextContent | ImageContent]:
    """Compile one template and render it."""
    try:
        scene_class, code = scenes.build(template_name, **params)
    except scenes.SceneSpecError as error:
        return _validation_failure(
            stage="validate", exception_type=type(error).__name__, message=str(error)
        )

    summary = SUMMARY_BUILDERS.get(template_name, lambda _: {})(params)

    return pipeline.execute(
        cfg,
        tool_name=template_name,
        code=code,
        scene_class=scene_class,
        quality=quality,
        title=title,
        args_summary=summary,
        run_id=workspace.new_run_id(),
        render_fn=render_fn,
        preview_fn=preview_fn,
    )


def _validation_failure(*, stage: str, exception_type: str, message: str):
    diagnostic = diagnostics.Diagnostic(stage=stage, type=exception_type, message=message)
    return envelope.content_blocks(
        envelope.failure_payload(run_id="", diagnostic=diagnostic)
    )
```

`manim-mcp/manim_mcp/tools/render.py`:

```python
"""The escape hatch: render whatever Manim code the model wrote.

`check` runs first so a syntax error or a missing `construct` is answered in
milliseconds rather than after a Manim process start.
"""

from __future__ import annotations

from typing import Callable

from mcp.types import ImageContent, TextContent

from .. import config as config_mod
from ..engine import diagnostics, workspace
from . import check as check_tool
from . import envelope, pipeline


def run_code(
    cfg: config_mod.Config,
    *,
    code: str,
    scene_name: str | None,
    quality: str,
    render_fn: Callable | None = None,
    preview_fn: Callable | None = None,
) -> list[TextContent | ImageContent]:
    """Validate, then render, raw Manim source."""
    verdict = check_tool.check_code(code)
    if not verdict["ok"]:
        return envelope.content_blocks(
            envelope.failure_payload(
                run_id="",
                diagnostic=diagnostics.Diagnostic(
                    stage="validate",
                    type="InvalidScene",
                    message="；".join(verdict["issues"]),
                ),
            )
        )

    available = verdict["sceneClasses"]
    chosen = scene_name or verdict.get("suggestedScene")
    if chosen not in available:
        return envelope.content_blocks(
            envelope.failure_payload(
                run_id="",
                diagnostic=diagnostics.Diagnostic(
                    stage="validate",
                    type="UnknownScene",
                    message=(
                        f"代码里没有名为 {chosen!r} 的场景类；"
                        f"可用的是：{', '.join(available)}"
                    ),
                ),
            )
        )

    return pipeline.execute(
        cfg,
        tool_name="render",
        code=code,
        scene_class=chosen,
        quality=quality,
        title=None,
        args_summary={"lines": len(code.splitlines())},
        run_id=workspace.new_run_id(),
        render_fn=render_fn,
        preview_fn=preview_fn,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_tool_declarative.py tests/test_tool_render.py -v`
Expected: PASS（19 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/tools/declarative.py manim-mcp/manim_mcp/tools/render.py tests/test_tool_declarative.py tests/test_tool_render.py
git commit -m "feat(manim-mcp): 声明式工具与代码逃生口"
```

---

## Task 18: `app.py` — FastMCP 组装

**Files:**
- Create: `manim-mcp/manim_mcp/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: 写失败测试**

`tests/test_app.py`:

```python
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


def test_selftest_returns_nonzero_when_a_dependency_is_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app, "build_server", lambda cfg: pytest.fail("must not start serving"))
    cfg = make_config(tmp_path)
    broken = app.replace(cfg, ffmpeg=None)
    assert app.selftest(broken) == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'manim_mcp.app'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/app.py`:

```python
"""FastMCP assembly.

Tool bodies are thin: they adapt MCP arguments into engine calls and never do
bookkeeping of their own, so every path ends in the same envelope and the same
content-block pair.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import sys
from typing import Literal

from fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from . import config as config_mod
from . import style as style_mod
from .tools import check as check_tool
from .tools import declarative, envelope
from .tools import render as render_tool
from .tools import runs as runs_tool
from .tools import style_guide as style_guide_tool

LOG = logging.getLogger("manim-mcp")

Quality = Literal["draft", "final"]

INSTRUCTIONS = (
    "把解释性动画渲染成视频。优先用 equation / graph / diagram / compare 四个模板："
    "它们只需要声明式参数，比手写 Manim 代码快得多也稳得多。"
    "只有四个模板都表达不了时才用 render 写原始代码；写代码前先用 check 花 0.1 秒体检，"
    "不要用一次 10 秒的渲染去发现一个语法错误。"
)


def replace(cfg: config_mod.Config, **changes) -> config_mod.Config:
    """A copy with the given fields replaced (used by tests and the self-test)."""
    return dataclasses.replace(cfg, **changes)


class Renderer:
    """Serialises renders and keeps blocking work off the event loop."""

    def __init__(self, cfg: config_mod.Config) -> None:
        self._cfg = cfg
        self._gate = asyncio.Semaphore(cfg.max_concurrency)

    async def run(self, work, *args, **kwargs):
        async with self._gate:
            return await asyncio.to_thread(work, self._cfg, *args, **kwargs)


def build_server(cfg: config_mod.Config) -> FastMCP:
    mcp = FastMCP("manim", instructions=INSTRUCTIONS)
    renderer = Renderer(cfg)

    @mcp.tool(
        name="equation",
        description=(
            "把一串 LaTeX 公式逐步变形，展示推导过程（3b1b 式）。"
            "steps 是 2-6 个 LaTeX 字符串，每一步一个状态。"
        ),
    )
    async def equation(
        steps: list[str],
        title: str | None = None,
        highlight: list[str] | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "equation",
            quality=quality,
            title=title,
            params={"steps": steps, "title": title, "highlight": highlight},
        )

    @mcp.tool(
        name="graph",
        description=(
            "函数图像，可叠加切线、面积填充与参数滑动。"
            "expressions 是 1-3 个 Python 表达式字符串，变量是 x，可用 np.*。"
        ),
    )
    async def graph(
        expressions: list[str],
        title: str | None = None,
        x_range: list[float] | None = None,
        y_range: list[float] | None = None,
        highlight: dict | None = None,
        parameter: dict | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "graph",
            quality=quality,
            title=title,
            params={
                "expressions": expressions,
                "title": title,
                "x_range": x_range,
                "y_range": y_range,
                "highlight": highlight,
                "parameter": parameter,
            },
        )

    @mcp.tool(
        name="diagram",
        description=(
            "流程 / 架构 / 因果关系的框图。nodes 是 [{id, label, kind}]，"
            "edges 是 [{from, to, label?}]；kind 取 process/decision/terminal/data。"
        ),
    )
    async def diagram(
        nodes: list[dict],
        edges: list[dict],
        title: str | None = None,
        layout: Literal["vertical", "horizontal"] = "vertical",
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "diagram",
            quality=quality,
            title=title,
            params={"nodes": nodes, "edges": edges, "title": title, "layout": layout},
        )

    @mcp.tool(
        name="compare",
        description=(
            "左右对照，突出两种做法或两个概念的差异。"
            "left/right 各是 {title, items}，items 为 1-5 条。"
        ),
    )
    async def compare(
        left: dict,
        right: dict,
        title: str | None = None,
        left_color: str | None = None,
        right_color: str | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            declarative.run_template,
            "compare",
            quality=quality,
            title=title,
            params={
                "left": left,
                "right": right,
                "title": title,
                "left_color": left_color,
                "right_color": right_color,
            },
        )

    @mcp.tool(
        name="render",
        description=(
            "逃生口：渲染任意 Manim 代码。code 必须是完整文件，含 `from manim import *` "
            "与至少一个 Scene 子类。调用前先用 check 体检。"
        ),
    )
    async def render(
        code: str,
        scene_name: str | None = None,
        quality: Quality = "draft",
    ) -> list[TextContent | ImageContent]:
        return await renderer.run(
            render_tool.run_code,
            code=code,
            scene_name=scene_name,
            quality=quality,
        )

    @mcp.tool(
        name="check",
        description=(
            "0.1 秒静态体检：语法、是否 import manim、是否有带 construct 的 Scene 子类。"
            "不渲染。写原始代码后应先调用它。"
        ),
    )
    async def check(code: str) -> list[TextContent | ImageContent]:
        return envelope.content_blocks(check_tool.check_code(code))

    @mcp.tool(
        name="style_guide",
        description=(
            "取本机的精确风格常量：调色板 hex、可用的中文字体名、Manim API 注意事项、"
            "4 个模板的参数说明、以及一段可直接改用的代码骨架。写代码前调用。"
        ),
    )
    async def style_guide() -> list[TextContent | ImageContent]:
        return envelope.content_blocks(
            style_guide_tool.style_guide_payload(style_mod.detect_cjk_font())
        )

    @mcp.tool(
        name="runs",
        description=(
            "查看历史渲染。action=list 列出最近的 run；action=get 配 runId 取回那次生成的"
            "完整 scene.py 源码，用于「把刚才那个动画改一下」。"
        ),
    )
    async def runs(
        action: Literal["list", "get"],
        run_id: str | None = None,
        limit: int = 20,
    ) -> list[TextContent | ImageContent]:
        return envelope.content_blocks(
            runs_tool.dispatch(cfg.render_root, action, run_id, limit)
        )

    return mcp


def selftest(cfg: config_mod.Config) -> int:
    """One real render, used by install.ps1 to prove the whole chain works."""
    from .tools import selftest as selftest_tool

    return selftest_tool.run(cfg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manim-mcp", description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="渲染一个样例场景后退出")
    args = parser.parse_args(argv)

    try:
        cfg = config_mod.load_config()
    except config_mod.ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        stream=sys.stderr,  # stdout carries the MCP frames and must stay clean
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    LOG.debug("resolved config: %s", cfg)

    if args.selftest:
        return selftest(cfg)

    build_server(cfg).run(transport="stdio", show_banner=False)
    return 0
```

> `app.selftest` 委托给 `tools/selftest.py`（Task 19 创建）。为让 **Task 18 的测试**通过，本任务先建一个最小可用版本：

`manim-mcp/manim_mcp/tools/selftest.py`:

```python
"""Placeholder replaced in Task 19."""

from __future__ import annotations

from .. import config as config_mod


def run(cfg: config_mod.Config) -> int:
    return 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/manim_mcp/app.py manim-mcp/manim_mcp/tools/selftest.py tests/test_app.py
git commit -m "feat(manim-mcp): FastMCP 工具注册"
```

---

## Task 19: `--selftest` — 真机端到端验收

**Files:**
- Modify: `manim-mcp/manim_mcp/tools/selftest.py`
- Test: `tests/test_selftest.py`

- [ ] **Step 1: 写失败测试**

`tests/test_selftest.py`:

```python
"""The self-test is the installer's proof; it must fail loudly, not politely."""

from pathlib import Path

from manim_mcp.config import Config
from manim_mcp.engine import workspace
from manim_mcp.tools import selftest


def make_config(tmp_path: Path, **overrides) -> Config:
    base = dict(
        python=r"D:\py\python.exe", manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe", render_root=tmp_path,
        max_concurrency=1, timeout_sec=30.0, gif_target_bytes=1000,
        gif_max_bytes=2000, keep_runs=50, log_level="INFO",
    )
    base.update(overrides)
    return Config(**base)


def test_missing_ffmpeg_exits_two_and_creates_no_run(tmp_path: Path):
    assert selftest.run(make_config(tmp_path, ffmpeg=None)) == 2
    assert workspace.existing_run_ids(tmp_path) == []


def test_successful_run_exits_zero_and_reports_artifacts(tmp_path: Path, capsys):
    from manim_mcp.engine.postprocess import Preview
    from manim_mcp.engine.render import RenderResult

    def fake_render(cfg, paths, scene_class, quality):
        artifact = paths.out / f"{scene_class}.mp4"
        artifact.write_bytes(b"mp4")
        return RenderResult(ok=True, mp4=artifact, seconds=4.2)

    def fake_preview(ffmpeg, mp4, out_dir, basename, **kwargs):
        path = out_dir / f"{basename}.gif"
        path.write_bytes(b"g" * 500)
        return Preview(path=path, kind="gif", byte_size=500)

    code = lambda: "from manim import *\n"  # noqa: E731
    assert selftest.run(
        make_config(tmp_path),
        build_code=code,
        render_fn=fake_render,
        preview_fn=fake_preview,
    ) == 0

    printed = capsys.readouterr().out
    assert "manim" in printed
    assert ".gif" in printed or ".mp4" in printed
    assert "self-test PASSED" in printed


def test_failed_render_exits_one_with_the_hint(tmp_path: Path, capsys):
    from manim_mcp.engine.diagnostics import Diagnostic
    from manim_mcp.engine.render import RenderResult

    def fake_render(cfg, paths, scene_class, quality):
        return RenderResult(
            ok=False, mp4=None, seconds=1.0,
            diagnostic=Diagnostic(stage="manim", type="NameError", message="boom", hint="加 import"),
        )

    assert selftest.run(
        make_config(tmp_path),
        build_code=lambda: "from manim import *\n",
        render_fn=fake_render,
    ) == 1
    captured = capsys.readouterr()
    assert "boom" in captured.out + captured.err
    assert "加 import" in captured.out + captured.err


def test_selftest_scene_uses_chinese_a_formula_and_a_shape():
    code = selftest.sample_scene("SimHei")
    assert "cn(" in code
    assert "MathTex" in code
    assert "Circle" in code
    assert "SimHei" in code


def test_selftest_scene_compiles_without_a_cjk_font():
    compile(selftest.sample_scene(None), "<selftest>", "exec")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_selftest.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'sample_scene'`

- [ ] **Step 3: 写实现**

`manim-mcp/manim_mcp/tools/selftest.py`:

```python
"""`--selftest`: render one real scene and report the whole chain.

install.ps1 runs this so a broken LaTeX install, a missing ffmpeg, or a bad render
root is discovered at install time rather than by a confused model later.
"""

from __future__ import annotations

import dataclasses
from typing import Callable

from .. import config as config_mod
from .. import style as style_mod
from ..engine import postprocess, render, workspace
from . import envelope

SAMPLE_SCENE_CLASS = "SelftestScene"

_SCENE = '''from manim import *

@@PREAMBLE@@


class SelftestScene(Scene):
    def construct(self):
        heading = cn("自检通过：中文渲染正常", TITLE_SIZE, WHITE).to_edge(UP, buff=0.8)
        formula = MathTex(r"e^{i\\pi} + 1 = 0")
        formula.next_to(heading, DOWN, buff=0.8)
        ring = Circle(radius=1.1, color=C_BLUE).next_to(formula, DOWN, buff=0.6)

        self.play(Write(heading), run_time=PLAY_RUN_TIME)
        self.play(FadeIn(formula, shift=UP * 0.4), run_time=PLAY_RUN_TIME)
        self.play(Create(ring), run_time=PLAY_RUN_TIME)
        self.wait(TAIL_WAIT)
'''


def sample_scene(cjk_font: str | None) -> str:
    return _SCENE.replace("@@PREAMBLE@@", style_mod.preamble(cjk_font))


def _dependency_problems(cfg: config_mod.Config) -> list[str]:
    problems: list[str] = []
    if not cfg.ffmpeg:
        problems.append("找不到 ffmpeg：GIF 预览无法生成（可用 MANIM_MCP_FFMPEG 显式指定绝对路径）")
    if not cfg.python:
        problems.append("找不到 Python 解释器")
    return problems


def run(
    cfg: config_mod.Config,
    *,
    build_code: Callable[[], str] | None = None,
    render_fn=None,
    preview_fn=None,
) -> int:
    """0 = healthy, 1 = render failed, 2 = a dependency is missing.

    Dependencies are checked *before* any directory is created, so a missing
    ffmpeg leaves no debris in the gallery.
    """
    print("manim-mcp self-test")
    print(f"  python      : {cfg.python}")
    print(f"  manim       : {cfg.manim or f'{cfg.python} -m manim'}")
    print(f"  ffmpeg      : {cfg.ffmpeg or '(missing)'}")
    print(f"  render root : {cfg.render_root}")

    problems = _dependency_problems(cfg)
    if problems:
        for problem in problems:
            print(f"  FAIL  {problem}")
        return 2

    font = style_mod.detect_cjk_font()
    print(f"  cjk font    : {font or '(none found; Chinese may render as boxes)'}")

    renderer = render_fn or render.render_scene
    try:
        paths = workspace.prepare_run(cfg.render_root, workspace.new_run_id())
        workspace.write_scene(
            paths, build_code() if build_code is not None else sample_scene(font)
        )
    except workspace.WorkspaceError as error:
        print(f"  FAIL  无法准备渲染目录：{error}")
        return 2

    outcome = renderer(cfg, paths, SAMPLE_SCENE_CLASS, "draft")

    if not outcome.ok or outcome.mp4 is None:
        diagnostic = outcome.diagnostic
        print("  FAIL  渲染未完成")
        if diagnostic is not None:
            print(f"        stage   : {diagnostic.stage}")
            print(f"        error   : {diagnostic.type}: {diagnostic.message}")
            if diagnostic.line:
                print(f"        line    : {diagnostic.line}")
            if diagnostic.hint:
                print(f"        hint    : {diagnostic.hint}")
        return 1

    print(f"  render      : OK in {outcome.seconds:.1f}s -> {outcome.mp4}")

    encoder = preview_fn or postprocess.build_preview
    preview = encoder(
        cfg.ffmpeg,
        outcome.mp4,
        paths.out,
        SAMPLE_SCENE_CLASS,
        target_bytes=cfg.gif_target_bytes,
        max_bytes=cfg.gif_max_bytes,
    )
    if preview.path is None:
        print("  preview     : 未生成（见上面的依赖问题）")
    else:
        print(f"  preview     : OK {preview.kind} {preview.byte_size} bytes -> {preview.path}")
        markdown = envelope.preview_markdown(preview.path)
        print(f"  markdown    : {markdown}")
    for note in preview.warnings:
        print(f"  warning     : {note}")

    print("  self-test PASSED")
    return 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_selftest.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 真机跑一次自检**

Run:
```powershell
$env:MANIM_MCP_RENDER_ROOT="D:\myprogram\dshplugin\renders"
D:\ProgramData\anaconda3\python.exe D:\myprogram\dshplugin\manim-mcp\server.py --selftest
```
Expected: 打印 `self-test PASSED`，`exit code 0`，并给出一个存在的 `.gif` 路径。
若打印 `FAIL 渲染未完成` 且 `hint` 指向 LaTeX，说明 MiKTeX 尚未预热——再跑一次即可（首次编译格式与宏包最慢）。

- [ ] **Step 6: 提交**

```bash
git add manim-mcp/manim_mcp/tools/selftest.py tests/test_selftest.py
git commit -m "feat(manim-mcp): --selftest 端到端自检"
```

---

## Task 20: 全量验收与 README

**Files:**
- Create: `manim-mcp/README.md`
- Create: `tests/manual/stdio_smoke.py`

- [ ] **Step 1: 跑全量测试**

Run: `python -m pytest -q`
Expected: 全部通过，0 failed。若个别失败，先修实现再继续（不要跳过）。

- [ ] **Step 2: 验证 stdio 协议层真的能启动**

`tests/test_app.py` 已用 FastMCP 的内存 Client 验证过工具注册，但那走的是进程内路径。这里额外验证**子进程 + stdio** 这条真实通路。

先把下面这段存成 `tests/manual/stdio_smoke.py`：

```python
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
```

Run: `python tests/manual/stdio_smoke.py`
Expected: 打印 `tools: [...]`（恰好 8 个）、`check ok: False ...`、`stdio smoke PASSED`，退出码 0。

> 这一步同时验证了「stdout 没有被 banner 或日志污染」——一旦 `show_banner` 或 `logging` 误写到 stdout，MCP 握手会在 `list_tools` 处直接失败。

（可选，需联网）也可以用 MCP Inspector 手动点一遍：
`npx -y @modelcontextprotocol/inspector <python> <server.py>`

- [ ] **Step 3: 用真实渲染验证四个模板各一次**

对每个模板跑一次真实渲染，逐个肉眼确认画面正确、中文无方框、公式无误：

| 模板 | 参数 |
|---|---|
| `equation` | `steps=[r"e^{i\pi} = \cos\theta + i\sin\theta", r"e^{i\pi} = -1", r"e^{i\pi} + 1 = 0"]`，`title="欧拉恒等式"` |
| `graph` | `expressions=["x**2"]`，`highlight={"x": 1.0, "tangent": True}` |
| `diagram` | `nodes=[{"id":"a","label":"输入"},{"id":"b","label":"处理"},{"id":"c","label":"输出"}]`，`edges=[{"from":"a","to":"b"},{"from":"b","to":"c"}]` |
| `compare` | `left={"title":"错误做法","items":["先写实现","再补测试"]}`，`right={"title":"推荐做法","items":["先写测试","再写实现"]}` |

在每个 run 的 `out\` 下确认 `.mp4` 与 `.gif` 都存在，且 `renders\index.json` 有 4 条记录。

- [ ] **Step 4: 写 `manim-mcp/README.md`**

内容必须包含：
1. 这个组件是什么、属于哪个项目（一句话指向 `..\README.md`）。
2. 依赖表（Python / Manim / MiKTeX / ffmpeg）与各自的验证命令。
3. 8 个工具的名称、一句话用途、必需参数。
4. 配置项表（与 Spec §14 完全一致）。
5. `--selftest` 的用法与三种退出码的含义。
6. 排错：按 `hint` 字段处理；MiKTeX 首次慢；`MANIM_MCP_*` 覆盖 PATH 问题。
7. `renders\` 布局与 `index.json` 的用途（面板会读它）。

- [ ] **Step 5: 提交**

```bash
git add manim-mcp/README.md tests/manual/stdio_smoke.py
git commit -m "docs(manim-mcp): 组件文档与 stdio 冒烟脚本"
```

---

## 执行期间的偏离记录

按 TDD 执行时发现计划本身的问题，已就地修正。**这些修正优先于上方对应步骤的原文。**

| # | 任务 | 计划原文的问题 | 实际采用的修正 |
|---|---|---|---|
| 1 | Task 1 | `tests/test_package.py` 里 `from manim_mcp import config` 引用了 Task 2 才创建的文件，Task 1 无法变绿 | 删掉该 import，Task 1 只断言包可导入与版本号 |
| 2 | Task 1 | `pytest.ini` 未设 `asyncio_default_fixture_loop_scope`，pytest-asyncio 每次输出 DeprecationWarning，违反「输出必须干净」 | 加上 `asyncio_default_fixture_loop_scope = function` |
| 3 | Task 4 | `RUN_ID_PATTERN` 固定 4 位 hex + `secrets.token_hex(2)`（16 位熵）。实测同一秒生成 50 个 id 出现碰撞 → **同一秒的两次渲染会覆盖彼此的 run 目录** | `token_hex(4)`（32 位熵），校验放宽为 `[0-9a-f]{4,8}`；新增「同一秒 500 个 id 不重复」的回归测试 |
| 4 | Task 5 | `save_index` 返回 `Path`，`upsert_run` 返回内存里的 `data`，其 `updatedAt` 是 `None`，与磁盘上的文件不一致 | `save_index` 改为返回**写入的确切 payload**；`upsert_run`/`remove_run` 直接返回它；新增「返回内容与磁盘一致」的断言 |
| 5 | Task 6 | `hint_for` 只把第 3 个参数（stderr blob）当匹配范围，`latex` 出现在异常 message 里时漏判（`test_hint_for_missing_latex_binary` 直接 TypeError） | 规则改读 `message + blob` 合并后的 haystack |
| 6 | Task 10 | `graph.py` 用 `json.dumps(list(x_range))` 生成区间字面量，浮点化后输出 `[-4.0, 4.0, 1.0]`，与 `PARAMS` 文档及 `test_default_x_range_is_used_when_absent` / `test_y_range_default_is_emitted` / `test_custom_x_range_is_emitted` 要求的 `[-4, 4, 1]` 不符（3 个测试红） | 新增 `_number` / `_range_literal`，整数值端点去掉 `.0`；`X_RANGE`/`Y_RANGE`/`AREA_RANGE` 统一改用 `_range_literal`（数值校验仍走 float，只修代码生成） |
| 7 | Task 11 | `test_node_kind_defaults_to_process` 断言 `'("x", "process")' in code`，但按计划的模板输出的是 `(id, label, kind)` 三元组 `("a", "x", "process")`，左括号在 id 之前，该子串永远无法匹配（测试自身写错，非实现错） | 断言改为完整三元组 `'("a", "x", "process")'`，同时钉死 id、label 与默认 kind，比原断言更强 |
| 8 | Task 11 | **只有真机渲染能发现的缺陷**：`diagram.py` 的 `_literal` 用 `json.dumps`，无边标签的边生成 `("in", "pivot", null)`。`ast.parse` **通过**（`null` 是合法标识符），但 Manim import 时 `NameError: name 'null' is not defined` | `style.py` 新增 `python_literal()`（正确处理 `None`/`True`/`False`），`diagram._literal` 委托给它；新增 `tests/test_scene_codegen.py` 对**全部四个模板**断言 AST 中不出现 `null`/`true`/`false` 这三个名字 |
| 9 | Task 11 | **画面目视验收发现的缺陷**：边以「方框中心 → 方框中心」直连，反向边（循环）直穿中间所有方框、标签压在节点上——框图反而更难读 | 正向边锚在相向的方框边缘（不穿框）；反向边沿列外侧弓形绕行（`path_arc`），标签移到列外 |
| 10 | Task 11 | **画面目视验收发现的缺陷**：方框宽度按 `0.34 * len(label)` 估算，这是拉丁字符的系数；中文标签（如「递归处理两侧」）贴到框边 | 模板内新增 `label_width()`，CJK 字符按约 1.9 倍字宽计（`ord(ch) > 0x2E80` 判定） |
| 11 | Task 14 | `check.py` 用字面量 `IMPORT_HINT not in code` 判断是否导入了 manim，于是 `import manim` + `class Demo(manim.Scene)` 这种**完全能渲染**的代码被判为「缺少 import」，`test_qualified_scene_base_is_recognised` 的 `ok is True` 无法满足（实现错，非测试错——该测试的意图正是「限定名基类应被识别」） | `check.py` 新增 AST 版 `_imports_manim()`：`import manim` / `import manim.*` / `from manim[.*] import ...` 都算已导入；issue 文案仍含 `from manim import *`，故 `test_missing_manim_import_is_reported` 不受影响 |
| 12 | Task 16 | `execute()` 无条件调用 `postprocess.probe_duration(cfg.ffmpeg, ...)`。`cfg.ffmpeg` 非空但该二进制不存在时（测试配置里就是假路径）`subprocess.run` 抛 `FileNotFoundError`，把一个已经成功的渲染变成未捕获异常——12 个 pipeline 测试全部红（实现错，且违反本文件自己写下的「次要步骤失败只降级为 warning」） | 时长探测包 `try/except`，失败降级为一条 warning 而不是抛出；**不改 `engine/postprocess.py`**（该模块已有测试且契约是「ffmpeg 说不出来就返回 0.0」，此处补的是调用侧的容错） |
| 13 | Task 13 / 14 / 17 | Step 4 的 `Expected: PASS（N passed）` 与计划自己给出的测试代码数量不符：Task 13 写 14（实际 13 个测试）、Task 14 写 16（实际 18 个）、Task 17 写 19（实际 17 个）。Task 15（12）与 Task 16（14）计数正确 | 以计划正文的测试代码为准执行，不为了让数字对上而增删断言；实际结果为 Task 13 = 13、Task 14 = 18、Task 17 = 17 |
| 14 | Task 16 / 8 | **审查发现的「修了一半」**：第 12 条只给直接调用的 `probe_duration` 加了 `try`，但同一个 `execute()` 里 `build_preview(...)` 同样会执行 ffmpeg，`cfg.ffmpeg` 指向不存在的文件时依然抛 `FileNotFoundError` 逃出工具。同理 `engine/render.py` 的 `spawn(...)` 在 `MANIM_MCP_MANIM` / `MANIM_MCP_PYTHON` 指向不存在的可执行文件时也抛 `FileNotFoundError` | `pipeline` 把**整个预览步骤**包进 `try/except`，失败降级为 warning + 空 `Preview`；`render_scene` 把 `spawn` 包进 `except OSError`，返回带可执行提示的 `Diagnostic`（`stage="manim"`，hint 指明检查 `MANIM_MCP_MANIM` / `MANIM_MCP_PYTHON`）。新增 3 个回归测试 |

> 第 14 条的教训：容器类修复要**按「谁会执行外部程序」找齐调用点**，而不是只修被测试直接打到的那一处。`cfg.ffmpeg`/`cfg.manim`/`cfg.python` 都是 install 脚本写入的绝对路径，任何一个变陈旧都会触发同一类崩溃。

**新增的验收工具**：`tests/manual/render_templates.py` —— 用真机 Manim 把四个模板（外加参数滑动的 graph）各渲染一次。第 8/9/10 条缺陷全是它发现的，而单元测试**全都漏掉了**。**改动 `manim_mcp/scenes/` 之后必须跑它。**

> 第 8 条的教训值得单独记一笔：`ast.parse` 通过并不代表代码能 import。任何把值编译成源码的地方（`scenes/`）都不能只用 `ast.parse` 断言，要么用 `python_literal()` 这类共享助手，要么真跑一次。

以下偏离是**预先设计**的，不属缺陷：Task 9 先建 `graph/diagram/compare` 三个抛 `SceneSpecError` 的占位模块（Task 10–12 替换）；Task 18 先建 `tools/selftest.py` 的 `return 0` 版（Task 19 替换）。

---

## 完成判据

Plan 1 完成的定义：

1. `python -m pytest -q` 全绿。
2. `python manim-mcp\server.py --selftest` 退出码 0，且打印出的 GIF 路径真实存在。
3. `python tests\manual\stdio_smoke.py` 退出码 0，工具列表恰好 8 个。
4. 四个模板各产出一次真实动画，`renders\index.json` 有对应记录。
5. 故意把一段坏代码喂给 `render`，返回的信封含正确的 `line` 与非空 `hint`。

后续计划：**Plan 2**（`dsh-manim-gallery` 面板插件）、**Plan 3**（Skill + install/uninstall + 端到端验收）。
