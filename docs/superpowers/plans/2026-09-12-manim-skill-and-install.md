# Skill + 安装接入（组件 3 + 集成）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已经建好的两个组件真正接进这台 DSH：(1) 写一个 Skill 教会模型「什么时候画、怎么画、画砸了怎么办」；(2) 写一个幂等的安装/卸载器，把 MCP 行、面板插件、Skill 三样东西挂上去，并且能干净地还原；(3) 在真实 DSH 页面上验收，直到对话里出现动画、左侧栏出现「动画库」。

**Architecture:** 用户面对的是两个 PowerShell 脚本（`install.ps1` / `uninstall.ps1`），但**所有会改文件的逻辑都在 Python 里**（`tools/dsh_installer.py`），因为那是可以被 pytest 精确断言的部分：YAML 块的手术、`package.json` 的编辑、`RENDER_ROOT` 的补丁、Skill 的复制，全部是「给一个沙盒路径 → 得到确定结果」的纯函数 + 一次应用。PowerShell 只做参数解析、依赖体检、调用 Python、打印结果。这样安排的原因很直接：在 PowerShell 里做保留注释的 YAML 手术并断言其正确性，比在 Python 里难得多，而安装器改的是**用户的 profile**，出错代价高。

**Tech Stack:** PowerShell 7（薄壳）、Python 3.13 + pytest（核心与测试）、PyYAML 6.0.3（只用于**校验**改完的 YAML 仍合法，不用于序列化——序列化会吃掉注释）、pnpm 11（建链接）。

**Spec:** `docs/superpowers/specs/2026-09-12-manim-visual-explainer-design.md`（§11 Skill 行为层、§13 安装与接入、§17 验收标准）

**前两份计划（必须已完成）:** `2026-09-12-manim-mcp-engine.md`（Plan 1）、`2026-09-12-manim-gallery-panel.md`（Plan 2）

---

## 关键事实（已查证）

| 事实 | 来源 |
|---|---|
| profile 的 bundles 写在 `~/.dsh/profiles/web/package.json` 的 `dsh.profile.bundles` 数组里；本地插件用 `dependencies` 的 `link:` 协议 + `node_modules` 符号链接 | 实读该文件 |
| 插件的 `node_modules` 条目是**符号链接**（`nodeLinker: hoisted`），pnpm 11.12.0 可用；`pnpm-lock.yaml` 已存在 | 实读 + `where pnpm` |
| MCP 挂载写在 `~/.dsh/profiles/web/cordis.patch.yml` 的 `- insert:` 条目里，形如 `{id, name, config}` | 实读该文件（已有 agentflow 与 game-poker 两行） |
| 该文件**带注释**（中文说明），所以不能用 YAML 反序列化再序列化的方式改它——注释会被吃掉 | 实读 |
| PyYAML 6.0.3 可用，用作改完之后的**合法性校验** | 实测 |
| **本机允许创建目录符号链接与 junction**（开发者模式已开），所以安装器可以直接建 `node_modules` 链接而不必依赖 pnpm | 实测 |
| Skill 装在 `~/.dsh/skills/<name>/`，与 `agentflow`、`agentkits-marketing` 等并列 | 实读 |
| MCP 工具的公开名是 `mcp__<serverName>__<rawName>`，即 `mcp__manim__equation` 等 8 个 | `dsh-mcp-client` 源码 |
| `~/.dsh/restart-web.ps1` 存在，是重启 web 的既有入口 | `$DSH_HOME` 列表 |
| Manim 行需要显式 `env`（DSH 会给子进程一个清洗过的环境）；`failOnStartupError: true` 让启动失败立刻暴露 | Plan 1 §13 |

---

## 文件结构

```
D:\myprogram\dshplugin\
├─ install.ps1                     用户入口：依赖体检 → 调 Python 核心 → 打印结果与重启提示
├─ uninstall.ps1                   用户入口：调 Python 核心做还原
├─ tools\
│  └─ dsh_installer.py                 全部会改文件的逻辑（纯函数 + apply），可被 pytest 精确断言
├─ skills\
│  └─ manim-explainer\
│     └─ SKILL.md                  行为层：何时画 / 选哪个工具 / 自愈协议 / 硬性要求
└─ tests\
   ├─ test_installer_paths.py      目标路径推导、YAML 块文本、package.json 编辑的纯函数
   ├─ test_installer_yaml.py       块插入/移除：保留注释、幂等、仍合法、其它条目字节不变
   ├─ test_installer_apply.py      apply_install / apply_uninstall 在沙盒里的往返一致
   └─ test_skill_doc.py            SKILL.md 的结构不变量（钉住工具名与必写章节，防止漂移）
```

**为什么把 installer 放在 `tools/` 而不是 `scripts/`**：`tools/` 下面已经有 `manim-mcp/manim_mcp/tools/`（MCP 工具），容易被混淆，所以这里用仓库根的 `tools/dsh_installer.py`，并在文件头注明它是**安装器**而不是 MCP 工具。它不属于 `manim_mcp` 包，因此 pytest 通过 `importlib` 按路径加载（Task 1 的 conftest 处理）。

---

## Task 1: 目标路径推导与三个文本变换的纯函数

**Files:**
- Create: `tools/dsh_installer.py`
- Modify: `tests/conftest.py`（把 `tools/` 加入 `sys.path`）
- Test: `tests/test_installer_paths.py`

- [ ] **Step 1: 让 `tools/` 可导入**

在 `tests/conftest.py` 末尾追加：

```python
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
```

- [ ] **Step 2: 写失败测试**

`tests/test_installer_paths.py`:

```python
"""The installer rewrites a user's profile, so every transformation is a pure,
separately assertable function rather than a side effect buried in a script.
"""

import json
from pathlib import Path

import pytest

from dsh_installer import (
    MANIM_BLOCK_ID,
    GALLERY_PACKAGE,
    PANEL_ID,
    InstallerError,
    Targets,
    build_manim_insert_block,
    patch_client_render_root,
    plan_package_json,
    remove_insert_block,
)


def targets(tmp_path: Path) -> Targets:
    return Targets(
        profile_root=tmp_path / "profile",
        plugin_root=tmp_path / "plugins",
        skill_root=tmp_path / "skills",
        source_root=tmp_path / "src",
        render_root=Path("D:/myprogram/dshplugin/renders"),
        python=r"D:\py\python.exe",
        manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe",
    )


def test_targets_derive_the_files_they_own(tmp_path: Path):
    subject = targets(tmp_path)
    assert subject.patch_file == tmp_path / "profile" / "cordis.patch.yml"
    assert subject.profile_package == tmp_path / "profile" / "package.json"
    assert subject.plugin_dir == tmp_path / "plugins" / GALLERY_PACKAGE
    assert subject.client_file == subject.plugin_dir / "lib" / "client.js"
    assert subject.skill_dir == tmp_path / "skills" / "manim-explainer"


def test_targets_reject_a_relative_render_root():
    with pytest.raises(InstallerError) as caught:
        Targets(
            profile_root=Path("p"), plugin_root=Path("l"), skill_root=Path("s"),
            source_root=Path("x"), render_root=Path("renders"),
            python="p", manim=None, ffmpeg=None,
        )
    assert "render_root" in str(caught.value)


def test_manim_block_names_the_server_and_pins_absolute_paths(tmp_path: Path):
    block = build_manim_insert_block(targets(tmp_path))
    assert f"id: {MANIM_BLOCK_ID}" in block
    assert "serverName: manim" in block
    assert "transport: stdio" in block
    assert "failOnStartupError: true" in block
    assert r"D:\py\python.exe" in block
    assert "MANIM_MCP_MANIM" in block
    assert "MANIM_MCP_FFMPEG" in block
    assert "MANIM_MCP_RENDER_ROOT" in block


def test_manim_block_is_a_valid_entry_in_a_top_level_sequence(tmp_path: Path):
    import yaml

    # The block is a snippet appended to a top-level sequence, so it is parsed as
    # the continuation of one. `"[]" + block` would be invalid YAML — a flow
    # sequence cannot be followed by a block sequence — hence the plain entry.
    parsed = yaml.safe_load("- id: connection\n" + build_manim_insert_block(targets(tmp_path)))
    assert [entry.get("id") for entry in parsed if "id" in entry] == ["connection"]
    inserts = [entry["insert"][0]["id"] for entry in parsed if "insert" in entry]
    assert inserts == [MANIM_BLOCK_ID]


def test_manim_block_omits_manim_when_it_was_not_found(tmp_path: Path):
    subject = targets(tmp_path)
    subject = subject.replace(manim=None)
    block = build_manim_insert_block(subject)
    assert "MANIM_MCP_MANIM" not in block
    assert "MANIM_MCP_PYTHON" in block


def test_remove_insert_block_leaves_a_file_without_it_untouched():
    text = "# header\n- id: connection\n  config: {}\n"
    assert remove_insert_block(text, MANIM_BLOCK_ID) == (text, False)


def test_remove_insert_block_drops_only_the_named_entry():
    text = (
        "# keep me\n"
        "- id: connection\n"
        "  config:\n"
        "    trustedHosts:\n"
        "      - a\n"
        "\n"
        "# manim MCP\n"
        "- insert:\n"
        "    - id: mcp-manim\n"
        "      name: '@deepseek-ai/dsh-mcp-client'\n"
        "\n"
        "# keep me too\n"
        "- insert:\n"
        "    - id: mcp-agentflow\n"
        "      name: '@deepseek-ai/dsh-mcp-client'\n"
    )
    stripped, removed = remove_insert_block(text, MANIM_BLOCK_ID)
    assert removed is True
    assert "mcp-manim" not in stripped
    assert "keep me" in stripped
    assert "keep me too" in stripped
    assert "mcp-agentflow" in stripped
    # The other entries survive verbatim.
    assert stripped.count("- insert:") == 1


def test_remove_insert_block_handles_an_entry_at_end_of_file():
    text = "- id: a\n- insert:\n    - id: mcp-manim\n      name: x\n"
    stripped, removed = remove_insert_block(text, MANIM_BLOCK_ID)
    assert removed is True
    assert stripped.strip() == "- id: a"


def test_remove_insert_block_keeps_the_comment_block_above_the_entry():
    """The comment above a row explains it; dropping the row should keep nothing
    of it, but it must not eat the unrelated comment above that."""
    text = "# unrelated\n- id: a\n\n# manim MCP — mine\n- insert:\n    - id: mcp-manim\n      name: x\n"
    stripped, _ = remove_insert_block(text, MANIM_BLOCK_ID)
    assert "# unrelated" in stripped
    assert "# manim MCP — mine" not in stripped


def test_plan_package_json_adds_bundle_and_link():
    original = json.dumps({
        "name": "dsh-profile-web",
        "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base"]}},
        "dependencies": {"@deepseek-ai/dsh-base": "^1.0.0"},
    }, indent=2)
    planned, changed = plan_package_json(original, plugin_dir=Path("C:/plug/dsh-manim-gallery"))
    assert changed is True
    data = json.loads(planned)
    assert data["dsh"]["profile"]["bundles"] == ["@deepseek-ai/dsh-base", GALLERY_PACKAGE]
    assert data["dependencies"][GALLERY_PACKAGE] == "link:C:/plug/dsh-manim-gallery"
    assert data["dependencies"]["@deepseek-ai/dsh-base"] == "^1.0.0"


def test_plan_package_json_is_idempotent():
    original = json.dumps({
        "name": "p",
        "dsh": {"profile": {"bundles": [GALLERY_PACKAGE]}},
        "dependencies": {GALLERY_PACKAGE: "link:C:/plug/dsh-manim-gallery"},
    }, indent=2)
    planned, changed = plan_package_json(original, plugin_dir=Path("C:/plug/dsh-manim-gallery"))
    assert changed is False
    assert json.loads(planned)["dsh"]["profile"]["bundles"] == [GALLERY_PACKAGE]


def test_plan_package_json_repoints_a_stale_link():
    original = json.dumps({
        "name": "p",
        "dsh": {"profile": {"bundles": [GALLERY_PACKAGE]}},
        "dependencies": {GALLERY_PACKAGE: "link:C:/somewhere/else"},
    }, indent=2)
    planned, changed = plan_package_json(original, plugin_dir=Path("C:/plug/dsh-manim-gallery"))
    assert changed is True
    assert json.loads(planned)["dependencies"][GALLERY_PACKAGE] == "link:C:/plug/dsh-manim-gallery"


def test_plan_package_json_refuses_a_bad_document():
    with pytest.raises(InstallerError):
        plan_package_json("{ not json", plugin_dir=Path("C:/plug"))


def test_plan_package_json_removal_restores_the_original_shape():
    original = json.dumps({
        "name": "p",
        "dsh": {"profile": {"bundles": ["a", GALLERY_PACKAGE]}},
        "dependencies": {"a": "1", GALLERY_PACKAGE: "link:C:/plug/dsh-manim-gallery"},
    }, indent=2)
    planned, changed = plan_package_json(
        original, plugin_dir=Path("C:/plug/dsh-manim-gallery"), remove=True
    )
    assert changed is True
    data = json.loads(planned)
    assert data["dsh"]["profile"]["bundles"] == ["a"]
    assert list(data["dependencies"]) == ["a"]


def test_patch_client_render_root_rewrites_the_one_line():
    source = 'const RENDER_ROOT = "D:/old/renders";\nconst PANEL_ID = "x";\n'
    patched, changed = patch_client_render_root(source, Path("D:/new/renders"))
    assert changed is True
    assert 'const RENDER_ROOT = "D:/new/renders";' in patched
    assert 'const PANEL_ID = "x";' in patched


def test_patch_client_render_root_uses_forward_slashes():
    patched, _ = patch_client_render_root(
        'const RENDER_ROOT = "D:/old";\n', Path(r"D:\new\renders")
    )
    assert "D:/new/renders" in patched
    assert "\\" not in patched.splitlines()[0]


def test_patch_client_render_root_is_idempotent():
    source = 'const RENDER_ROOT = "D:/new/renders";\n'
    patched, changed = patch_client_render_root(source, Path("D:/new/renders"))
    assert changed is False
    assert patched == source


def test_patch_client_render_root_refuses_to_guess():
    with pytest.raises(InstallerError) as caught:
        patch_client_render_root("const OTHER = 1;\n", Path("D:/new"))
    assert "RENDER_ROOT" in str(caught.value)


def test_panel_id_matches_the_one_plan_two_registers():
    """The sidebar entry id and the `main` key are the same string in Plan 2."""
    assert PANEL_ID == "manim-gallery"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_paths.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer'`

- [ ] **Step 4: 写实现**

`tools/dsh_installer.py`:

```python
"""Installer core for the Manim visual-explainer plugin set.

This is NOT an MCP tool module. It rewrites the user's DSH profile, so every
transformation is a pure function of its inputs: the planning functions return the
text that *would* be written and a flag saying whether anything changed, and only
`apply_install` / `apply_uninstall` touch the disk. That split is what lets the
tests assert on the risky part — YAML surgery that must preserve comments, and a
`package.json` edit that must not disturb the entries it does not own.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

MANIM_BLOCK_ID = "mcp-manim"
GALLERY_PACKAGE = "dsh-manim-gallery"
PANEL_ID = "manim-gallery"
SKILL_NAME = "manim-explainer"

RENDER_ROOT_LINE_RE = re.compile(r'^(?P<indent>\s*)const RENDER_ROOT = "(?P<value>[^"]*)";$', re.MULTILINE)
# A row inside `- insert:` is identified by its `id:` line; the entry runs from the
# `- insert:` header above it to the next top-level `- ` line (or EOF).
TOP_LEVEL_ENTRY_RE = re.compile(r"^- ", re.MULTILINE)


class InstallerError(RuntimeError):
    """The installer cannot proceed; the message is meant for a human."""


@dataclass(frozen=True)
class Targets:
    """Every path the installer reads or writes."""

    profile_root: Path
    plugin_root: Path
    skill_root: Path
    source_root: Path
    render_root: Path
    python: str
    manim: str | None
    ffmpeg: str | None

    def __post_init__(self) -> None:
        if not self.render_root.is_absolute():
            raise InstallerError(
                f"render_root must be absolute, got {self.render_root!r}; "
                "the panel and the MCP must agree on one root"
            )

    def replace(self, **changes) -> "Targets":
        return dataclasses.replace(self, **changes)

    @property
    def patch_file(self) -> Path:
        return self.profile_root / "cordis.patch.yml"

    @property
    def profile_package(self) -> Path:
        return self.profile_root / "package.json"

    @property
    def plugin_dir(self) -> Path:
        return self.plugin_root / GALLERY_PACKAGE

    @property
    def client_file(self) -> Path:
        return self.plugin_dir / "lib" / "client.js"

    @property
    def host_entry(self) -> Path:
        return self.plugin_dir / "lib" / "index.js"

    @property
    def skill_dir(self) -> Path:
        return self.skill_root / SKILL_NAME

    @property
    def module_link(self) -> Path:
        return self.profile_root / "node_modules" / GALLERY_PACKAGE


def _yaml_scalar(value: str) -> str:
    """Single-quote a path so Windows backslashes and colons stay literal."""
    return "'" + value.replace("'", "''") + "'"


def build_manim_insert_block(targets: Targets) -> str:
    """The `- insert:` entry that mounts the Manim MCP.

    Every path is pinned: DSH hands the MCP child a scrubbed environment, so a
    value that is only reachable through PATH may simply be absent.
    """
    env_lines = [
        f"          MANIM_MCP_PYTHON: {_yaml_scalar(targets.python)}",
    ]
    if targets.manim:
        env_lines.append(f"          MANIM_MCP_MANIM: {_yaml_scalar(targets.manim)}")
    if targets.ffmpeg:
        env_lines.append(f"          MANIM_MCP_FFMPEG: {_yaml_scalar(targets.ffmpeg)}")
    env_lines.append(
        f"          MANIM_MCP_RENDER_ROOT: {_yaml_scalar(targets.render_root.as_posix())}"
    )

    server = targets.source_root / "manim-mcp" / "server.py"
    return "\n".join(
        [
            "# manim MCP — Manim 可视化解释插件（由 install.ps1 维护，可重复执行）",
            "- insert:",
            f"    - id: {MANIM_BLOCK_ID}",
            "      name: '@deepseek-ai/dsh-mcp-client'",
            "      config:",
            "        serverName: manim",
            "        transport: stdio",
            f"        command: {_yaml_scalar(targets.python)}",
            "        args:",
            f"          - {_yaml_scalar(str(server))}",
            "        failOnStartupError: true",
            "        env:",
            *env_lines,
            "",
        ]
    )


def remove_insert_block(text: str, block_id: str) -> tuple[str, bool]:
    """Drop the `- insert:` entry whose row carries `id: block_id`.

    Returns `(new_text, removed)`. Comment preservation is why this is line-based
    rather than a YAML round-trip: the file explains each row in Chinese comments,
    and deserialising would silently delete every one of them.
    """
    lines = text.splitlines(keepends=True)
    marker = re.compile(rf"^\s*-\s*id:\s*{re.escape(block_id)}\s*$")

    for index, line in enumerate(lines):
        if not marker.match(line.rstrip("\r\n")):
            continue

        # Walk back to the `- insert:` header that owns this row.
        start = index
        while start > 0 and not lines[start].startswith("- "):
            start -= 1
        if not lines[start].startswith("- "):
            raise InstallerError(f"found id: {block_id} but no owning top-level entry")

        # The entry ends at the next top-level `- ` line, and the blank lines and
        # comment lines directly above the entry belong to it.
        end = len(lines)
        for cursor in range(start + 1, len(lines)):
            if lines[cursor].startswith("- "):
                end = cursor
                break

        head = start
        while head > 0 and lines[head - 1].lstrip().startswith("#"):
            head -= 1
        while head > 0 and lines[head - 1].strip() == "":
            head -= 1

        tail = end
        while tail < len(lines) and lines[tail].strip() == "":
            tail += 1

        return "".join(lines[:head] + lines[tail:]), True

    return text, False


def plan_package_json(
    text: str, *, plugin_dir: Path, remove: bool = False
) -> tuple[str, bool]:
    """Add or remove the gallery plugin's bundle entry and `link:` dependency."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise InstallerError(f"profile package.json is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise InstallerError("profile package.json must be a JSON object")

    before = json.dumps(data, sort_keys=True)

    profile = data.setdefault("dsh", {}).setdefault("profile", {})
    bundles = profile.setdefault("bundles", [])
    dependencies = data.setdefault("dependencies", {})
    link = f"link:{plugin_dir.as_posix()}"

    if remove:
        if GALLERY_PACKAGE in bundles:
            bundles.remove(GALLERY_PACKAGE)
        dependencies.pop(GALLERY_PACKAGE, None)
    else:
        if GALLERY_PACKAGE not in bundles:
            bundles.append(GALLERY_PACKAGE)
        dependencies[GALLERY_PACKAGE] = link

    changed = json.dumps(data, sort_keys=True) != before
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n", changed


def patch_client_render_root(text: str, render_root: Path) -> tuple[str, bool]:
    """Point the installed panel at the same render root the MCP writes to."""
    wanted = render_root.as_posix()
    match = RENDER_ROOT_LINE_RE.search(text)
    if match is None:
        raise InstallerError(
            "lib/client.js has no `const RENDER_ROOT = \"...\";` line; "
            "the panel and the MCP would disagree about where the runs live"
        )
    if match.group("value") == wanted:
        return text, False
    replaced = RENDER_ROOT_LINE_RE.sub(
        lambda m: f'{m.group("indent")}const RENDER_ROOT = "{wanted}";', text, count=1
    )
    return replaced, True
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_paths.py -q`
Expected: PASS（20 passed）

- [ ] **Step 6: 提交**

```bash
git add tools/dsh_installer.py tests/test_installer_paths.py tests/conftest.py
git commit -m "feat(installer): 目标路径推导与三个文本变换的纯函数"
```

---

## Task 2: 应用安装 / 卸载（沙盒往返一致）

**Files:**
- Modify: `tools/dsh_installer.py`
- Test: `tests/test_installer_apply.py`

- [ ] **Step 1: 写失败测试**

`tests/test_installer_apply.py`:

```python
"""Install then uninstall must return the profile to byte-identical text.

That property is the whole safety argument for letting a script touch ~/.dsh, so
it is asserted on real files in a sandbox rather than reasoned about.
"""

import json
import shutil
from pathlib import Path

import pytest

from dsh_installer import (
    GALLERY_PACKAGE,
    InstallerError,
    Targets,
    apply_install,
    apply_uninstall,
    plan_install,
    plan_uninstall,
)

PROFILE_PATCH = """\
# Your patch layer for this dsh profile.
- id: connection
  config:
    trustedHosts:
      - example.com

# agentflow MCP — per docs/dsh-setup.md
- insert:
    - id: mcp-agentflow
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: agentflow
"""

PROFILE_PACKAGE = json.dumps(
    {
        "name": "dsh-profile-web",
        "private": True,
        "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", "dsh-harvest"]}},
        "dependencies": {
            "@deepseek-ai/dsh-base": "1.0.0",
            "dsh-harvest": "link:C:/Users/x/.dsh/plugins/dsh-harvest/dsh-harvest",
        },
    },
    indent=2,
) + "\n"


@pytest.fixture()
def sandbox(tmp_path: Path) -> Targets:
    profile = tmp_path / "profile"
    (profile / "node_modules").mkdir(parents=True)
    (profile / "cordis.patch.yml").write_text(PROFILE_PATCH, encoding="utf-8")
    (profile / "package.json").write_text(PROFILE_PACKAGE, encoding="utf-8")

    source = tmp_path / "src"
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "dsh-manim-gallery",
        source / GALLERY_PACKAGE,
        ignore=shutil.ignore_patterns("test", "node_modules"),
    )
    (source / "manim-mcp").mkdir()
    (source / "manim-mcp" / "server.py").write_text("# entry\n", encoding="utf-8")
    (source / "skills" / "manim-explainer").mkdir(parents=True)
    (source / "skills" / "manim-explainer" / "SKILL.md").write_text("# skill\n", encoding="utf-8")

    return Targets(
        profile_root=profile,
        plugin_root=tmp_path / "plugins",
        skill_root=tmp_path / "skills",
        source_root=source,
        render_root=tmp_path / "renders",
        python=r"D:\py\python.exe",
        manim=r"D:\py\Scripts\manim.exe",
        ffmpeg=r"D:\tools\ffmpeg.exe",
    )


def test_plan_install_describes_every_step_without_touching_anything(sandbox: Targets):
    before = sandbox.patch_file.read_text(encoding="utf-8")
    plan = plan_install(sandbox)
    assert sandbox.patch_file.read_text(encoding="utf-8") == before
    kinds = [step["kind"] for step in plan["steps"]]
    assert kinds == [
        "backup",
        "yaml-insert",
        "copy-plugin",
        "patch-package-json",
        "patch-render-root",
        "link-package",
        "copy-skill",
        "verify-selftest",
    ]
    assert plan["changed"] is True


def test_plan_install_is_idempotent_after_apply(sandbox: Targets):
    apply_install(sandbox)
    again = plan_install(sandbox)
    flags = {step["kind"]: step for step in again["steps"]}
    assert flags["patch-package-json"]["changed"] is False
    assert flags["patch-render-root"]["changed"] is False
    assert flags["copy-plugin"]["changed"] is False
    assert flags["copy-skill"]["changed"] is False
    assert flags["link-package"]["changed"] is False
    # The MCP row is always replaced (remove + append is how idempotence works),
    # so it is the one step that legitimately still reports a change.
    assert flags["yaml-insert"]["replaced"] is True
    assert again["changed"] is False


def test_apply_install_mounts_the_mcp_without_disturbing_other_entries(sandbox: Targets):
    apply_install(sandbox)
    text = sandbox.patch_file.read_text(encoding="utf-8")
    assert "mcp-manim" in text
    assert "serverName: manim" in text
    assert "# agentflow MCP — per docs/dsh-setup.md" in text
    assert "id: mcp-agentflow" in text
    assert "example.com" in text

    import yaml

    parsed = yaml.safe_load(text)
    assert isinstance(parsed, list)
    assert [entry.get("id") for entry in parsed if "id" in entry] == ["connection"]
    inserts = [entry["insert"][0]["id"] for entry in parsed if "insert" in entry]
    assert inserts == ["mcp-agentflow", "mcp-manim"]


def test_apply_install_writes_a_backup_next_to_the_patch_file(sandbox: Targets):
    apply_install(sandbox)
    backups = list(sandbox.profile_root.glob("cordis.patch.yml.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == PROFILE_PATCH


def test_apply_install_adds_the_bundle_and_the_link(sandbox: Targets):
    apply_install(sandbox)
    data = json.loads(sandbox.profile_package.read_text(encoding="utf-8"))
    assert data["dsh"]["profile"]["bundles"] == ["@deepseek-ai/dsh-base", "dsh-harvest", GALLERY_PACKAGE]
    assert data["dependencies"][GALLERY_PACKAGE] == f"link:{sandbox.plugin_dir.as_posix()}"
    assert data["dependencies"]["dsh-harvest"].startswith("link:")


def test_apply_install_copies_the_plugin_and_patches_its_render_root(sandbox: Targets):
    apply_install(sandbox)
    assert sandbox.host_entry.exists()
    assert sandbox.client_file.exists()
    text = sandbox.client_file.read_text(encoding="utf-8")
    assert f'const RENDER_ROOT = "{sandbox.render_root.as_posix()}";' in text
    # The plugin's test directory is not part of the installed artifact.
    assert not (sandbox.plugin_dir / "test").exists()


def test_apply_install_copies_the_skill(sandbox: Targets):
    apply_install(sandbox)
    assert (sandbox.skill_dir / "SKILL.md").read_text(encoding="utf-8") == "# skill\n"


def test_apply_install_reruns_cleanly(sandbox: Targets):
    apply_install(sandbox)
    first = sandbox.patch_file.read_text(encoding="utf-8")
    apply_install(sandbox)
    second = sandbox.patch_file.read_text(encoding="utf-8")
    assert first == second
    assert second.count("mcp-manim") == 1


def test_uninstall_restores_both_files_byte_for_byte(sandbox: Targets):
    apply_install(sandbox)
    apply_uninstall(sandbox)
    assert sandbox.patch_file.read_text(encoding="utf-8") == PROFILE_PATCH
    assert sandbox.profile_package.read_text(encoding="utf-8") == PROFILE_PACKAGE
    assert not sandbox.plugin_dir.exists()
    assert not sandbox.skill_dir.exists()


def test_uninstall_leaves_unrelated_entries_alone_when_never_installed(sandbox: Targets):
    apply_uninstall(sandbox)
    assert sandbox.patch_file.read_text(encoding="utf-8") == PROFILE_PATCH
    assert sandbox.profile_package.read_text(encoding="utf-8") == PROFILE_PACKAGE


def test_uninstall_keeps_renders_by_default(sandbox: Targets):
    apply_install(sandbox)
    rendered = sandbox.render_root / "20260912-153012-a1b2" / "out" / "S.gif"
    rendered.parent.mkdir(parents=True)
    rendered.write_bytes(b"gif")
    apply_uninstall(sandbox)
    assert rendered.exists()


def test_plan_uninstall_reports_what_it_would_remove(sandbox: Targets):
    apply_install(sandbox)
    plan = plan_uninstall(sandbox)
    kinds = [step["kind"] for step in plan["steps"]]
    assert kinds == [
        "backup",
        "yaml-remove",
        "remove-package-json-entry",
        "remove-plugin-dir",
        "remove-skill-dir",
        "unlink-package",
    ]
    flags = {step["kind"]: step for step in plan["steps"]}
    assert flags["yaml-remove"]["present"] is True
    assert flags["remove-plugin-dir"]["changed"] is True
    assert plan["changed"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_apply.py -q`
Expected: FAIL — `ImportError: cannot import name 'apply_install' from 'installer'`

- [ ] **Step 3: 写实现**

在 `tools/dsh_installer.py` 末尾追加：

```python
@dataclass
class Step:
    """One planned filesystem action."""

    kind: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"kind": self.kind, **self.detail}


def _timestamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d%H%M%S")


def _read(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def plan_install(targets: Targets) -> dict:
    """Everything `apply_install` will do, as data.

    Every step is always listed, each carrying its own `changed` flag. Filtering
    the list down to "what actually changes" reads better but cannot be asserted
    on: a re-install still has to *replace* the MCP row (removing it and appending
    it again is how idempotence is achieved), so the row appears either way.
    """
    patch_text = _read(targets.patch_file)
    _, replaced = remove_insert_block(patch_text, MANIM_BLOCK_ID)

    package_text = _read(targets.profile_package)
    _, package_changed = plan_package_json(package_text, plugin_dir=targets.plugin_dir)

    render_root_wanted = f'const RENDER_ROOT = "{targets.render_root.as_posix()}";'
    render_root_changed = render_root_wanted not in _read(targets.client_file)

    steps = [
        Step("backup", {"path": str(targets.patch_file)}),
        Step("yaml-insert", {"id": MANIM_BLOCK_ID, "replaced": replaced}),
        Step(
            "copy-plugin",
            {
                "from": str(targets.source_root / GALLERY_PACKAGE),
                "to": str(targets.plugin_dir),
                "changed": not targets.plugin_dir.exists(),
            },
        ),
        Step("patch-package-json", {"changed": package_changed}),
        Step(
            "patch-render-root",
            {"changed": render_root_changed or not targets.client_file.exists()},
        ),
        Step(
            "link-package",
            {
                "package": GALLERY_PACKAGE,
                "cwd": str(targets.profile_root),
                "changed": not targets.module_link.exists(),
            },
        ),
        Step(
            "copy-skill",
            {
                "from": str(targets.source_root / "skills" / SKILL_NAME),
                "to": str(targets.skill_dir),
                "changed": not targets.skill_dir.exists(),
            },
        ),
        Step(
            "verify-selftest",
            {
                "command": [
                    targets.python,
                    str(targets.source_root / "manim-mcp" / "server.py"),
                    "--selftest",
                ]
            },
        ),
    ]
    changed = any(step.detail.get("changed") is True for step in steps)
    return {"action": "install", "changed": changed, "steps": [step.as_dict() for step in steps]}


def plan_uninstall(targets: Targets) -> dict:
    patch_text = _read(targets.patch_file)
    _, present = remove_insert_block(patch_text, MANIM_BLOCK_ID)
    _, package_changed = plan_package_json(
        _read(targets.profile_package), plugin_dir=targets.plugin_dir, remove=True
    )
    steps = [
        Step("backup", {"path": str(targets.patch_file)}),
        Step("yaml-remove", {"id": MANIM_BLOCK_ID, "present": present, "changed": present}),
        Step("remove-package-json-entry", {"changed": package_changed}),
        Step(
            "remove-plugin-dir",
            {"path": str(targets.plugin_dir), "changed": targets.plugin_dir.exists()},
        ),
        Step(
            "remove-skill-dir",
            {"path": str(targets.skill_dir), "changed": targets.skill_dir.exists()},
        ),
        Step(
            "unlink-package",
            {
                "package": GALLERY_PACKAGE,
                "cwd": str(targets.profile_root),
                "changed": targets.module_link.exists() or targets.module_link.is_symlink(),
            },
        ),
    ]
    changed = any(step.detail.get("changed") is True for step in steps)
    return {"action": "uninstall", "changed": changed, "steps": [step.as_dict() for step in steps]}


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    target = path.with_name(f"{path.name}.bak-{_timestamp()}")
    shutil.copy2(path, target)
    return target


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def apply_install(targets: Targets, *, copy_plugin: bool = True, link: bool = True) -> dict:
    """Perform the install. Returns the plan that was executed."""
    plan = plan_install(targets)
    _backup(targets.patch_file)

    stripped, _ = remove_insert_block(_read(targets.patch_file), MANIM_BLOCK_ID)
    if stripped and not stripped.endswith("\n"):
        stripped += "\n"
    _write(targets.patch_file, stripped + build_manim_insert_block(targets))

    if copy_plugin:
        if targets.plugin_dir.exists():
            shutil.rmtree(targets.plugin_dir)
        shutil.copytree(
            targets.source_root / GALLERY_PACKAGE,
            targets.plugin_dir,
            ignore=shutil.ignore_patterns("test", "node_modules", "__pycache__"),
        )

    package_path = targets.profile_package
    _backup(package_path)
    planned, _ = plan_package_json(_read(package_path), plugin_dir=targets.plugin_dir)
    _write(package_path, planned)

    # Guarded because `--skip-copy` runs exist for the file-surgery tests, and
    # `patch_client_render_root` refuses to guess when the line is absent.
    if targets.client_file.exists():
        patched, _ = patch_client_render_root(
            _read(targets.client_file), targets.render_root
        )
        _write(targets.client_file, patched)

    source_skill = targets.source_root / "skills" / SKILL_NAME
    if source_skill.exists():
        if targets.skill_dir.exists():
            shutil.rmtree(targets.skill_dir)
        shutil.copytree(source_skill, targets.skill_dir)

    if link:
        _link_package(targets)
    return plan


def apply_uninstall(targets: Targets, *, purge_renders: bool = False) -> dict:
    plan = plan_uninstall(targets)
    _backup(targets.patch_file)

    stripped, _ = remove_insert_block(_read(targets.patch_file), MANIM_BLOCK_ID)
    _write(targets.patch_file, stripped)

    package_path = targets.profile_package
    if package_path.exists():
        _backup(package_path)
        planned, _ = plan_package_json(
            _read(package_path), plugin_dir=targets.plugin_dir, remove=True
        )
        _write(package_path, planned)

    shutil.rmtree(targets.plugin_dir, ignore_errors=True)
    shutil.rmtree(targets.skill_dir, ignore_errors=True)
    _unlink_package(targets)
    if purge_renders:
        shutil.rmtree(targets.render_root, ignore_errors=True)
    return plan


def _link_package(targets: Targets) -> None:
    """Create the node_modules link pnpm would create for a `link:` dependency.

    Done directly rather than by shelling out to pnpm: the link is one symlink,
    and requiring a package manager to install a local directory would make the
    installer fail on a machine that has node but not pnpm.
    """
    targets.profile_root.mkdir(parents=True, exist_ok=True)
    node_modules = targets.profile_root / "node_modules"
    node_modules.mkdir(parents=True, exist_ok=True)
    link = targets.module_link
    if link.is_symlink() or link.exists():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink(missing_ok=True)
    try:
        link.symlink_to(targets.plugin_dir, target_is_directory=True)
    except OSError as error:
        raise InstallerError(
            f"cannot create the node_modules link {link}: {error}. "
            "On Windows this needs Developer Mode or an elevated shell; "
            "alternatively run `pnpm install` in the profile directory."
        ) from error


def _unlink_package(targets: Targets) -> None:
    link = targets.module_link
    try:
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
    except OSError:
        pass
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_apply.py -q`
Expected: PASS（13 passed）

- [ ] **Step 5: 提交**

```bash
git add tools/dsh_installer.py tests/test_installer_apply.py
git commit -m "feat(installer): 安装/卸载编排与沙盒往返一致"
```

---

## Task 3: `install.ps1` / `uninstall.ps1` 薄壳与 `--dry-run`

**Files:**
- Create: `install.ps1`
- Create: `uninstall.ps1`
- Test: `tests/test_installer_cli.py`

- [ ] **Step 1: 写失败测试**

`tests/test_installer_cli.py`:

```python
"""The entry points must be safe to run twice and safe to ask questions of.

`--dry-run` is the only way to see what an installer will do to your profile
before it does it, so it is tested as a first-class feature rather than a flag.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "tools" / "dsh_installer.py"


def run(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALLER), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.fixture()
def sandbox(tmp_path: Path):
    profile = tmp_path / "profile"
    (profile / "node_modules").mkdir(parents=True)
    (profile / "cordis.patch.yml").write_text("- id: connection\n", encoding="utf-8")
    (profile / "package.json").write_text(
        json.dumps({"name": "p", "dsh": {"profile": {"bundles": []}}, "dependencies": {}}),
        encoding="utf-8",
    )
    source = tmp_path / "src"
    shutil.copytree(
        REPO / "dsh-manim-gallery",
        source / "dsh-manim-gallery",
        ignore=shutil.ignore_patterns("test", "node_modules"),
    )
    (source / "manim-mcp").mkdir()
    (source / "manim-mcp" / "server.py").write_text("# entry\n", encoding="utf-8")
    (source / "skills" / "manim-explainer").mkdir(parents=True)
    (source / "skills" / "manim-explainer" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    return tmp_path, profile, source


def common(sandbox) -> list[str]:
    tmp_path, profile, source = sandbox
    return [
        "--profile-root", str(profile),
        "--plugin-root", str(tmp_path / "plugins"),
        "--skill-root", str(tmp_path / "skills"),
        "--source-root", str(source),
        "--render-root", str(tmp_path / "renders"),
        "--python", sys.executable,
    ]


def test_dry_run_prints_a_json_plan_and_changes_nothing(sandbox):
    tmp_path, profile, _ = sandbox
    before = (profile / "cordis.patch.yml").read_text(encoding="utf-8")
    result = run("install", *common(sandbox), "--dry-run")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout[result.stdout.index("{"):])
    assert plan["action"] == "install"
    assert plan["changed"] is True
    assert (profile / "cordis.patch.yml").read_text(encoding="utf-8") == before
    assert not (tmp_path / "plugins").exists()


def test_apply_then_dry_run_reports_nothing_left_to_do(sandbox):
    run("install", *common(sandbox))
    result = run("install", *common(sandbox), "--dry-run")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout[result.stdout.index("{"):])
    assert plan["changed"] is False
    flags = {step["kind"]: step for step in plan["steps"]}
    assert flags["copy-plugin"]["changed"] is False
    assert flags["patch-package-json"]["changed"] is False


def test_uninstall_dry_run_changes_nothing(sandbox):
    run("install", *common(sandbox))
    _, profile, _ = sandbox
    installed = (profile / "cordis.patch.yml").read_text(encoding="utf-8")
    result = run("uninstall", *common(sandbox), "--dry-run")
    assert result.returncode == 0, result.stderr
    assert (profile / "cordis.patch.yml").read_text(encoding="utf-8") == installed


def test_missing_source_is_a_clear_failure(tmp_path: Path):
    result = run(
        "install",
        "--profile-root", str(tmp_path / "p"),
        "--plugin-root", str(tmp_path / "l"),
        "--skill-root", str(tmp_path / "s"),
        "--source-root", str(tmp_path / "absent"),
        "--render-root", str(tmp_path / "r"),
        "--python", sys.executable,
        "--dry-run",
    )
    assert result.returncode != 0
    assert "source-root" in (result.stdout + result.stderr)


def test_a_relative_render_root_is_refused(sandbox):
    """The panel and the MCP must agree on one absolute root, or the panel is empty."""
    args = common(sandbox)
    args[args.index("--render-root") + 1] = "renders"
    result = run("install", *args, "--dry-run")
    assert result.returncode != 0
    assert "absolute" in (result.stdout + result.stderr)


def test_the_powershell_entry_point_is_a_thin_wrapper():
    """The pwsh file must not reimplement the file surgery it delegates to Python.

    Asserted on *code*, not on words: the script's own help text explains that it
    does not touch YAML, so a naive `"yaml" in text` check would fail on the
    comment that describes the design.
    """
    text = (REPO / "install.ps1").read_text(encoding="utf-8-sig")
    assert "dsh_installer.py" in text
    assert '"install"' in text
    # A reimplementation would parse or write the profile itself.
    for forbidden in ("ConvertFrom-Json", "ConvertFrom-Yaml", "Set-Content", "Out-File", "Add-Content"):
        assert forbidden not in text, f"install.ps1 reimplements {forbidden}"

    uninstall = (REPO / "uninstall.ps1").read_text(encoding="utf-8-sig")
    assert "dsh_installer.py" in uninstall
    assert '"uninstall"' in uninstall
    assert "ConvertFrom-Json" not in uninstall
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_cli.py -q`
Expected: FAIL — installer 没有 `main()`，退出码非 0 且 stdout 里没有 JSON

- [ ] **Step 3: 写实现**

在 `tools/dsh_installer.py` 末尾追加：

```python
def _add_common_arguments(parser) -> None:
    parser.add_argument("--profile-root", required=True, type=Path)
    parser.add_argument("--plugin-root", type=Path, default=Path.home() / ".dsh" / "plugins")
    parser.add_argument("--skill-root", type=Path, default=Path.home() / ".dsh" / "skills")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--render-root", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--manim", default=None)
    parser.add_argument("--ffmpeg", default=None)
    parser.add_argument("--dry-run", action="store_true")


def _targets_from(args) -> Targets:
    source = args.source_root.resolve()
    if not (source / GALLERY_PACKAGE).is_dir():
        raise InstallerError(
            f"--source-root {source} does not contain {GALLERY_PACKAGE}/; "
            "point it at the directory that holds this repository"
        )
    if not (source / "manim-mcp" / "server.py").is_file():
        raise InstallerError(f"--source-root {source} does not contain manim-mcp/server.py")
    return Targets(
        profile_root=args.profile_root,
        plugin_root=args.plugin_root,
        skill_root=args.skill_root,
        source_root=source,
        render_root=args.render_root,
        python=args.python,
        manim=args.manim,
        ffmpeg=args.ffmpeg,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="installer",
        description="Mount or remove the Manim explainer MCP, panel, and skill.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    _add_common_arguments(subparsers.add_parser("install"))
    uninstall = subparsers.add_parser("uninstall")
    _add_common_arguments(uninstall)
    uninstall.add_argument("--purge-renders", action="store_true")

    args = parser.parse_args(argv)
    try:
        targets = _targets_from(args)
        if args.action == "install":
            plan = plan_install(targets) if args.dry_run else apply_install(targets)
        else:
            plan = (
                plan_uninstall(targets)
                if args.dry_run
                else apply_uninstall(targets, purge_renders=args.purge_renders)
            )
    except InstallerError as error:
        print(f"installer: {error}", file=sys.stderr)
        return 2

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

顶部 import 区加上：

```python
import argparse
import sys
```

`install.ps1`:

```powershell
<#
.SYNOPSIS
  把 Manim 可视化解释插件挂到这台 DSH 上。

.DESCRIPTION
  依赖体检 → 调用 tools\dsh_installer.py 做真正的挂载 → 打印结果与重启提示。
  所有会改文件的逻辑都在 Python 里（可被 pytest 精确断言）；这个脚本只负责
  参数解析、体检和转述，不自己碰 YAML 或 JSON。

.EXAMPLE
  .\install.ps1
  .\install.ps1 -DryRun          # 只打印将要做的改动，不写任何文件
#>
[CmdletBinding()]
param(
    [switch] $DryRun,
    [string] $ProfileRoot = (Join-Path $HOME ".dsh\profiles\web"),
    [string] $PluginRoot  = (Join-Path $HOME ".dsh\plugins"),
    [string] $SkillRoot   = (Join-Path $HOME ".dsh\skills"),
    [string] $RenderRoot  = (Join-Path $PSScriptRoot "renders")
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot

function Require-Command([string] $Name, [string] $Hint) {
    $found = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $found) { throw "找不到 $Name。$Hint" }
    return $found.Source
}

Write-Host "Manim 可视化解释插件 — 安装" -ForegroundColor Cyan

$python = Require-Command "python" "安装 Python 3.11+ 并确保它在 PATH 上。"
$manim  = (Get-Command "manim" -ErrorAction SilentlyContinue).Source
$ffmpeg = (Get-Command "ffmpeg" -ErrorAction SilentlyContinue).Source
if (-not $manim)  { Write-Warning "PATH 上没有 manim；安装器会退回 'python -m manim'，请确认 manim 可被导入。" }
if (-not $ffmpeg) { Write-Warning "PATH 上没有 ffmpeg；GIF 预览将无法生成（MP4 不受影响）。" }

$arguments = @(
    (Join-Path $repo "tools\dsh_installer.py"), "install",
    "--profile-root", $ProfileRoot,
    "--plugin-root",  $PluginRoot,
    "--skill-root",   $SkillRoot,
    "--source-root",  $repo,
    "--render-root",  $RenderRoot,
    "--python",       $python
)
if ($manim)  { $arguments += @("--manim",  $manim) }
if ($ffmpeg) { $arguments += @("--ffmpeg", $ffmpeg) }
if ($DryRun) { $arguments += "--dry-run" }

& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "installer 退出码 $LASTEXITCODE" }

if ($DryRun) {
    Write-Host "`n以上是 dry-run，没有写入任何文件。" -ForegroundColor Yellow
} else {
    Write-Host "`n安装完成。**必须重启 dsh web 才会生效**：" -ForegroundColor Green
    Write-Host "  & `"$HOME\.dsh\restart-web.ps1`""
    Write-Host "重启后应能看到：左侧栏多出一个「动画库」图标；对话里问一个值得画的问题会内嵌动画。"
}
```

`uninstall.ps1`:

```powershell
<#
.SYNOPSIS
  把 Manim 可视化解释插件从这台 DSH 上摘干净。

.DESCRIPTION
  与 install.ps1 对称：调用 tools\dsh_installer.py 还原 cordis.patch.yml 与
  package.json，删除插件目录与 Skill 副本。默认**保留**已经渲染出的动画
  （它们是用户的产物，不该被卸载脚本删掉）。

.EXAMPLE
  .\uninstall.ps1
  .\uninstall.ps1 -DryRun
  .\uninstall.ps1 -PurgeRenders
#>
[CmdletBinding()]
param(
    [switch] $DryRun,
    [switch] $PurgeRenders,
    [string] $ProfileRoot = (Join-Path $HOME ".dsh\profiles\web"),
    [string] $PluginRoot  = (Join-Path $HOME ".dsh\plugins"),
    [string] $SkillRoot   = (Join-Path $HOME ".dsh\skills"),
    [string] $RenderRoot  = (Join-Path $PSScriptRoot "renders")
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot

$python = (Get-Command "python" -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "找不到 python。" }

$arguments = @(
    (Join-Path $repo "tools\dsh_installer.py"), "uninstall",
    "--profile-root", $ProfileRoot,
    "--plugin-root",  $PluginRoot,
    "--skill-root",   $SkillRoot,
    "--source-root",  $repo,
    "--render-root",  $RenderRoot,
    "--python",       $python
)
if ($DryRun)      { $arguments += "--dry-run" }
if ($PurgeRenders) { $arguments += "--purge-renders" }

& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "installer 退出码 $LASTEXITCODE" }

if (-not $DryRun) {
    Write-Host "`n已卸载。`renders\` 目录已保留（用 -PurgeRenders 才会删除）。" -ForegroundColor Green
    Write-Host "重启 dsh web 后左侧栏的「动画库」图标会消失。"
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_cli.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 手工确认 PowerShell 薄壳能跑起来（dry-run）**

Run:
```powershell
cd D:\myprogram\dshplugin
.\install.ps1 -DryRun -ProfileRoot "$env:TEMP\manim-profile-probe" -PluginRoot "$env:TEMP\manim-plugins-probe" -SkillRoot "$env:TEMP\manim-skills-probe" -RenderRoot "D:\myprogram\dshplugin\renders"
```
Expected: 打印 JSON 计划，`"action": "install"`，退出码 0；`$env:TEMP\manim-profile-probe` **不存在**（dry-run 不建目录）。
若报「未签名脚本无法运行」，用 `pwsh -ExecutionPolicy Bypass -File .\install.ps1 ...`。

- [ ] **Step 6: 提交**

```bash
git add install.ps1 uninstall.ps1 tools/dsh_installer.py tests/test_installer_cli.py
git commit -m "feat(installer): PowerShell 入口与 --dry-run"
```

---

## Task 4: SKILL.md 行为层

**Files:**
- Create: `skills/manim-explainer/SKILL.md`
- Test: `tests/test_skill_doc.py`

- [ ] **Step 1: 写失败测试**

`tests/test_skill_doc.py`:

```python
"""The Skill is the model's only instruction set for this capability.

It is prose, so it cannot be unit-tested for correctness — but it CAN be tested for
the two ways it rots: naming a tool that no longer exists, and losing a rule that
the whole feature depends on. Both have happened in equivalent documents.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "manim-explainer" / "SKILL.md"
TEXT = SKILL.read_text(encoding="utf-8")

TOOL_RAW_NAMES = ("equation", "graph", "diagram", "compare", "render", "check", "style_guide", "runs")


def test_the_skill_has_frontmatter_with_a_name_and_a_description():
    assert TEXT.startswith("---\n")
    frontmatter = TEXT.split("---", 2)[1]
    assert re.search(r"^name:\s*manim-explainer\s*$", frontmatter, re.MULTILINE)
    description = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    assert description, "the description is what the router reads to decide whether to load this"
    assert len(description.group(1).strip()) > 40


def test_the_description_carries_the_trigger_words_the_router_matches_on():
    frontmatter = TEXT.split("---", 2)[1].lower()
    for word in ("动画", "manim", "可视化", "看不懂"):
        assert word in frontmatter, f"missing trigger word {word!r}"


@pytest.mark.parametrize("raw_name", TOOL_RAW_NAMES)
def test_every_tool_the_engine_exposes_is_named(raw_name: str):
    """A skill that names a renamed tool sends the model into a dead call."""
    assert f"mcp__manim__{raw_name}" in TEXT, f"{raw_name} is not mentioned"


def test_no_tool_is_invented():
    mentioned = set(re.findall(r"mcp__manim__([a-z_]+)", TEXT))
    assert mentioned <= set(TOOL_RAW_NAMES), f"unknown tools: {mentioned - set(TOOL_RAW_NAMES)}"


def test_the_decision_tree_maps_each_tool_to_its_situation():
    for marker in ("公式", "函数", "流程", "对照"):
        assert marker in TEXT


def test_the_self_heal_protocol_states_a_retry_limit():
    assert "2 次" in TEXT or "两次" in TEXT
    assert "check" in TEXT


def test_the_self_heal_protocol_forbids_silent_surrender():
    assert "绝不" in TEXT or "不得" in TEXT


def test_the_preview_requirement_is_explicit():
    """Without this line the animation exists but the user never sees it."""
    assert "previewMarkdown" in TEXT


def test_the_one_sentence_requirement_is_present():
    """An animation without a sentence naming the relation it shows is decoration."""
    assert "一句话" in TEXT


def test_the_budget_guardrail_is_present():
    assert "最多 1 个" in TEXT or "最多一个" in TEXT


def test_the_draft_quality_default_is_stated():
    assert "draft" in TEXT


def test_the_failure_isolation_rule_is_present():
    assert "不阻塞" in TEXT or "照常" in TEXT


def test_the_skill_tells_the_model_to_stop_animating_static_facts():
    assert "闲聊" in TEXT or "不画" in TEXT


def test_the_default_duration_is_stated():
    assert "8" in TEXT and "20" in TEXT
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_skill_doc.py -q`
Expected: FAIL — `FileNotFoundError: .../skills/manim-explainer/SKILL.md`

- [ ] **Step 3: 写 SKILL.md**

`skills/manim-explainer/SKILL.md` 必须包含下面**全部**内容。这不是提纲，是要写进去的东西：

```markdown
---
name: manim-explainer
description: 用 Manim 现做一段动画来解释「关系与过程」——数学推导、算法执行、函数行为、流程结构、对错对比。当回答里出现这类内容，或用户说「看不懂」「太抽象」「演示一下」「画个图」时使用。动画会直接内嵌在回答里。
---

# 用动画解释，而不是用更多文字解释

纯文本在两类内容上会失效：**时序**（谁先谁后、一步怎么变成下一步）和**空间关系**（谁包含谁、哪里变大变小）。读者被迫在脑中重建这些东西，而这正是理解成本最高的地方。一张 10 秒的动画把这件事直接做掉。

但动画不等于帮助。**一张没有点明「它在说明什么关系」的图，只是装饰。**

## 什么时候画

**默认主动**：只要这一轮回答的核心内容落在下面任一类，就直接画，不要问用户要不要。

- 数学推导、公式证明、变形过程
- 算法执行过程、数据结构操作、递归展开
- 函数行为、几何直觉、极限与逼近
- 流程、架构、状态机、因果链
- 「错误做法 vs 正确做法」这类对比
- 用户说「看不懂」「太抽象」「演示一下」「画个图」时

**不画**：闲聊、纯事实查询、纯代码编辑、单纯的文件操作，以及动画明显比一句话更慢的场景。

## 选哪个工具

决策树，从上往下第一个匹配的即选它：

| 内容 | 工具 |
|---|---|
| 一串公式逐步变形 | `mcp__manim__equation` |
| 函数图像，带切线 / 面积 / 参数滑动 | `mcp__manim__graph` |
| 流程、架构、因果，节点加箭头 | `mcp__manim__diagram` |
| 左右对照两种做法或两个概念 | `mcp__manim__compare` |
| 上面四个都表达不了 | `mcp__manim__render`（写原始 Manim 代码） |

两个辅助工具：

- 写**原始代码**之前先调 `mcp__manim__style_guide` 拿本机的配色、**可用中文字体名**、API 注意事项和一段可直接改的骨架。
- 写完之后、渲染之前先调 `mcp__manim__check` 花 0.1 秒体检语法与结构。**不要用一次 10 秒的渲染去发现一个语法错误。**
- 想改上一次的动画时，用 `mcp__manim__runs` 取回那次生成的源码，而不是凭记忆重写。

## 渲染失败怎么办

失败返回里有 `error.line`（出错行号）、`error.sourceLine`（那一行的源码）和 `hint`（最可能的修法）。

1. 读 `hint` 与 `line`，**只改需要改的地方**，重试。**最多 2 次。**
2. 两次都失败就**停止重试**，改用文字或静态图把这件事讲清楚，并把 `codePath` 附上供排查。
3. **绝不静默放弃**，也绝不让「动画生成失败」成为回答的全部内容。

先用 `check` 再 `render`，能把自愈的代价从 10 秒降到 0.1 秒。

## 硬性要求

1. **回答里必须包含返回的 `previewMarkdown`**，原样粘贴。不贴，用户就看不到动画——那一轮渲染白做了。
2. **动画前后各写一句话**，点明这张图在说明什么关系。没有这句话，动画不提升理解。
3. **一轮回答最多 1 个动画。** 多次渲染会拖慢回答，也会让重点被淹没。
4. **默认用 `draft` 画质。** 只有用户明确要「高清」「最终版」才用 `final`。
5. **渲染失败不影响正文。** 正文照常给出，附一句说明与代码路径，不要卡在动画上。
6. **同一个概念不重复画。** 本会话里已经画过的同类动画不要再画，除非用户要求或内容实质不同。

## 风格红线

- 深色背景，配色统一走 `style_guide` 给出的调色板。
- **一个动画只讲一个想法。** 总时长控制在 8-20 秒。
- 中文必须走 `cn()` 或用字体名，否则会渲染成方框——`style_guide` 会给出本机可用的中文字体。
- 代码要扁平，避免自定义类与复杂继承：这段代码之后可能由你自己读回来修改。
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin; D:\ProgramData\anaconda3\python.exe -m pytest tests/test_skill_doc.py -q`
Expected: PASS（20 passed）

- [ ] **Step 5: 提交**

```bash
git add skills/manim-explainer/SKILL.md tests/test_skill_doc.py
git commit -m "feat(skill): manim-explainer 行为层（触发策略 / 决策树 / 自愈协议 / 硬性要求）"
```

---

## Task 5: 真实安装到这台 DSH

**Files:**
- Create: `README.md`（仓库根的总体说明）
- Modify: 无（真正的改动在 `~/.dsh` 下，由脚本执行）

- [ ] **Step 1: 跑一次 dry-run，逐条核对将要发生的改动**

Run:
```powershell
cd D:\myprogram\dshplugin
.\install.ps1 -DryRun
```
Expected: JSON 计划里有 `yaml-insert{replaced: false}`、`copy-plugin`、`patch-package-json{changed: true}`、`copy-skill`；`renders\` 下没有被创建任何东西；`~/.dsh` 下**没有任何文件被修改**（用 `git status` 无关；改看 `~/.dsh/profiles/web/cordis.patch.yml` 的 mtime）。

- [ ] **Step 2: 备份确认**

手工确认这两个文件当前的内容被记录下来了，安装后要能对照还原：
- `~/.dsh/profiles/web/cordis.patch.yml`
- `~/.dsh/profiles/web/package.json`

- [ ] **Step 3: 真实安装**

Run:
```powershell
cd D:\myprogram\dshplugin
.\install.ps1
```
Expected:
- 脚本打印依赖体检结果与 JSON 计划，退出码 0
- `~/.dsh/profiles/web/cordis.patch.yml` 多出一个 `mcp-manim` 的 `- insert:` 条目，且**原有注释与 agentflow / game-poker 两行原样保留**
- `~/.dsh/profiles/web/cordis.patch.yml.bak-<时间戳>` 存在
- `~/.dsh/profiles/web/package.json` 的 `dsh.profile.bundles` 末尾多出 `dsh-manim-gallery`，`dependencies` 里多出 `"dsh-manim-gallery": "link:C:/.../plugins/dsh-manim-gallery"`
- `~/.dsh/profiles/web/node_modules/dsh-manim-gallery` 是指向 `~/.dsh/plugins/dsh-manim-gallery` 的符号链接
- `~/.dsh/plugins/dsh-manim-gallery/lib/client.js` 里的 `RENDER_ROOT` 是 `D:/myprogram/dshplugin/renders`
- `~/.dsh/skills/manim-explainer/SKILL.md` 存在

- [ ] **Step 4: 校验配置文件仍然合法**

Run:
```powershell
D:\ProgramData\anaconda3\python.exe -c "import yaml,json,pathlib; p=pathlib.Path.home()/'.dsh/profiles/web'; print('patch entries:', len(yaml.safe_load((p/'cordis.patch.yml').read_text(encoding='utf-8')))); d=json.loads((p/'package.json').read_text(encoding='utf-8')); print('bundles:', d['dsh']['profile']['bundles'])"
```
Expected: 打印条目数与 bundles 列表；**不抛异常**。

- [ ] **Step 5: 重启 dsh web**

Run: `& "$HOME\.dsh\restart-web.ps1"`
Expected: 脚本报告重启成功。等它稳定（约 10 秒）再打开 `http://127.0.0.1:3080`。

- [ ] **Step 6: 确认 MCP 起来了**

在这台 DSH 里新开一个会话，让 agent 列出模型可见的工具名。
Expected: 能看到 `mcp__manim__equation` / `graph` / `diagram` / `compare` / `render` / `check` / `style_guide` / `runs` 共 8 个。
若没有：看 dsh 的启动日志里有没有 `mcp-client(manim)` 的报错——`failOnStartupError: true` 会让它显式失败而不是静默无工具。

- [ ] **Step 7: 写仓库根的 README.md**

`README.md` 必须包含：

1. **一句话**：这是什么（让 DSH 里的模型用 Manim 现做动画来解释回答），以及它由三个组件构成。
2. **组件表**：`manim-mcp`（渲染引擎）/ `dsh-manim-gallery`（面板）/ `skills/manim-explainer`（行为层），各自一句话职责与所在目录。
3. **安装**：`.\install.ps1`（先 `-DryRun` 看计划），以及**必须重启 dsh web**。
4. **卸载**：`.\uninstall.ps1`，说明 `renders\` 默认保留。
5. **它改了你 profile 里的哪两样东西**：明确写出 `cordis.patch.yml` 加一行、`package.json` 加一项，并指出备份文件的位置。
6. **依赖**：Python 3.11+ / Manim Community / MiKTeX / ffmpeg，以及各自的验证命令。
7. **文档索引**：Spec 与三份计划的路径。
8. **排错入口**：对话里不出动画 → 先跑 `manim-mcp\server.py --selftest`；面板不出现 → 检查 bundles 与符号链接；面板显示读不到 → 检查 `RENDER_ROOT`。

- [ ] **Step 8: 提交**

```bash
git add README.md
git commit -m "docs: 仓库总说明（组件、安装、卸载、依赖与排错）"
```

---

## Task 6: 端到端验收

**Files:**
- Modify: 无（验收记录写进 `docs/superpowers/plans/` 同目录的验收记录，或直接回报）

- [ ] **Step 1: 对话内动画**

在 DSH 里新开一个会话，问一个**值得画**的问题，例如：

> 为什么 e^{iπ} + 1 = 0？

Expected:
- 回答正文里有一句话点明动画在说明什么
- 正文里有一张**会动的图**（GIF 内嵌）
- 回答里能看到 `mcp__manim__equation` 的工具调用卡片
- `renders\<runId>\out\` 下有 `.mp4` 与 `.gif`

若不内嵌：把工具返回里的 `previewMarkdown` 原样贴进地址栏同级路径试 `/api/file?path=...`，确认不是 401。

- [ ] **Step 2: 动画库面板**

点左侧栏的「动画库」图标。
Expected:
- 中央面板打开，网格里出现刚渲染的那条动画，缩略图**会动**
- 顶部有搜索框、类型下拉、排序下拉、「显示失败」开关、刷新按钮
- 点卡片进详情：出现带原生控件的 `<video>`，能播放、能拖进度
- 搜索标题关键词能筛出它；按类型筛选能筛出它；排序切换有反应
- 点「复制路径」能把路径写进剪贴板

- [ ] **Step 3: 多模板与中文**

再问三个分别落在 `graph` / `diagram` / `compare` 的问题（例如「画出 x² 在 x=1 处的切线」「画出快速排序的分治流程」「对比先写测试和先写实现」）。
Expected: 三次都出动画，中文无方框，画面里**没有箭头穿框或标签压字**。四条记录都出现在面板里。

- [ ] **Step 4: 自愈路径**

让 agent 用 `mcp__manim__render` 渲染一段**故意写错**的代码（例如调用一个不存在的类）。
Expected: 工具返回里含 `error.type`、`error.line`、`error.sourceLine` 与**非空的中文 hint**；agent 能据此改对并重试成功。若 hint 为空，说明真机 traceback 解析又退化了（见 Plan 1 偏离 #16）。

- [ ] **Step 5: 失败不阻塞**

让 agent 渲染一段**怎么改都渲染不出来**的代码（例如引用一个不存在的字体）。
Expected: 最多重试 2 次后放弃，**正文照常给出**，附一句说明与 `codePath`；回答里没有「动画生成失败」以外的空白。

- [ ] **Step 6: 只读边界**

在面板上找一圈。
Expected: **没有任何删除或重渲染入口**。确认 `lib/client.js` 里没有 POST/DELETE 请求（`tests/test_installer_paths.py` 与 Plan 2 的 `view.test.mjs` 已各钉一道，这里做人工确认）。

- [ ] **Step 7: 卸载往返**

Run:
```powershell
cd D:\myprogram\dshplugin
.\uninstall.ps1 -DryRun    # 先看计划
.\uninstall.ps1
```
Expected:
- `~/.dsh/profiles/web/cordis.patch.yml` 与安装前**逐字节一致**（与 Task 5 Step 2 记录的内容对比）
- `~/.dsh/profiles/web/package.json` 同理
- `~/.dsh/plugins/dsh-manim-gallery` 与 `~/.dsh/skills/manim-explainer` 已删除
- `~/.dsh/profiles/web/node_modules/dsh-manim-gallery` 链接已移除
- **`renders\` 里的动画还在**
- 重启 web 后面板图标消失，对话里不再有 `mcp__manim__*` 工具

- [ ] **Step 8: 重新装回来**

Run: `.\install.ps1` 然后重启 web。
Expected: 面板与工具都回来，**`renders\` 里原有的动画仍全部在面板里**（证明卸载没有破坏产物、索引仍能对账）。

---

## 执行期间的偏离记录

按 TDD 执行时发现计划本身的问题，已就地修正。**这些修正优先于上方对应步骤的原文。**

| # | 任务 | 计划原文的问题 | 实际采用的修正 |
|---|---|---|---|
| 1 | Task 1 | 计划里的模块名是 `installer`，而 PyPI 上存在同名包——`import installer` 会解析到 site-packages 里那个无关的包，测试**碰巧**通过 | 模块改名为 `dsh_installer`（`tools/dsh_installer.py`），测试与 `install.ps1` 同步 |
| 2 | Task 1 / 3 | 早期 `python dsh_installer.py install …` 在 `main()` 尚不存在时**以退出码 0 空转**，让一条本该失败的 CLI 测试通过 | 测试加强为断言 `mcp-manim` 真的落进了 `cordis.patch.yml`，而不是只看退出码 |
| 3 | Task 4 | SKILL.md 的硬性要求写「回答里**必须**包含 `previewMarkdown`」，但引擎在产物落在渲染根之外时会合法地返回 `null`（见 Plan 1 偏离 20） | 拆成两条：非 `null` 时必须**原样**粘贴（改一个字符就会 404）；为 `null` 时**不得伪造**引用，照常给正文并说明动画在工具卡片里。`tests/test_skill_doc.py` 增加 `test_the_preview_requirement_covers_the_null_case` |
| 4 | Task 4 / 5 | 计划未涉及文件系统解析基准。正文内嵌动画依赖「`fs-sandbox.cwd` 与产物同盘符」，缺这一步则正文里每个动画都 404 | 新增 `build_fs_overlay_block`，把 `fs-sandbox.cwd` 钉到 `renders/` 的父目录；`plan_uninstall` 用同一 id 移除。`test_installer_apply.py` 断言它会随安装落地、随卸载消失、且重装时逐字幂等 |
| 5 | Task 6 | 计划 Step 6 之后没有留下**可重复**的正文通道验收手段（此前是手工看浏览器） | 新增 `tests/manual/probe_file_api.mjs`：用本机 browser-session secret 签一个真 cookie，对运行中的 Host 发 `HEAD /api/file`，对照新/旧引用形式并核对字节数。它把「动画在正文里到底能不能加载」从目视变成了可重跑的命令 |
| 6 | Task 6 Step 7–8 | 计划要求做一次完整的卸载→重装往返 | **尚未执行**（属破坏性操作，会短暂移除工具与面板）。卸载前的快照已存于 `C:\Users\15775\.dsh\manim-install-before.txt`（2282 字节），沙盒内的逐字节往返一致性由 `test_installer_apply.py` 覆盖；真机往返待用户确认时机 |

---

## 完成判据

| # | 判据 | 由谁证明 |
|---|---|---|
| 1 | `python -m pytest -q` 全绿（含三个 installer 测试文件与 skill 文档测试） | Task 1–4 |
| 2 | `install.ps1 -DryRun` 打印 JSON 计划且不写任何文件 | Task 3 Step 5 |
| 3 | 安装后 `cordis.patch.yml` 仍是合法 YAML，且原有注释与另两个 `- insert:` 条目原样保留 | Task 5 Step 4 |
| 4 | 安装后 `package.json` 是合法 JSON，bundles 与 dependencies 各多一项，其余不动 | Task 5 Step 3–4 |
| 5 | 重启 web 后 8 个 `mcp__manim__*` 工具可见 | Task 5 Step 6 |
| 6 | 对话里出现**会动的**内嵌动画，且正文有一句话点明它 | Task 6 Step 1 |
| 7 | 左侧栏出现「动画库」，网格缩略图会动，详情能播 MP4 | Task 6 Step 2 |
| 8 | 四个模板都能出动画，中文无方框，画面无箭头穿框/标签压字 | Task 6 Step 3 |
| 9 | 坏代码返回非空中文 hint，agent 能据此改对 | Task 6 Step 4 |
| 10 | 渲染彻底失败时正文照常给出，不阻塞 | Task 6 Step 5 |
| 11 | 面板没有任何写操作入口 | Task 6 Step 6 |
| 12 | `uninstall.ps1` 后两个配置文件逐字节还原，产物保留 | Task 6 Step 7 |
| 13 | 重装后历史动画仍全部在面板里 | Task 6 Step 8 |

**这 13 条全部满足，这个插件才算真的做完了。**
