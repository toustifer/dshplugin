# 通用文件发布通道 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让模型能把任意本地文件（视频/音频/PDF/图片/其它）发布到对话流里内嵌呈现，用户不需要额外操作。

**Architecture:** 一个仅依赖标准库的 stdio MCP（`media-mcp`）提供 `publish_file`：校验路径 → 嗅探 MIME → 分类 → 算出同源引用 → （PDF 额外光栅化前 3 页）→ 返回 JSON 信封。一个手写打包的 DSH client 插件（`dsh-media-view`）注册 `tool.call.toolview`（key = `mcp__media__publish_file`），从工具结果的文本块里解析信封并按 kind 渲染。

**Tech Stack:** Python 3.13（`mcp` / `fastmcp` 已装）、纯 JavaScript（无构建步骤，`window.__ModuleLoader__.load` 格式）、React（由 module loader 提供）、`pdftoppm`（MiKTeX 自带）、pytest、node:test。

**设计依据：** `docs/superpowers/specs/2026-09-14-media-publish-channel-design.md`。本计划的每一步都必须与该规格一致；冲突时以规格为准并回来改计划。

**关键不变量（违反任何一条都会导致"引用永远 404"）：**
1. 引用的形式是**去掉盘符的完整绝对路径**（`D:\a\b.mp4` → `/a/b.mp4`）。
2. `fs-sandbox.cwd` 必须与产物**同盘符**。全仓库只有**一个**变量决定它。
3. 渲染器注册的 key 必须**逐字**是 `mcp__media__publish_file`。打错不会报错，只是永远不渲染。

---

## 文件结构

| 路径 | 职责 |
|---|---|
| `media-mcp/server.py` | stdio 启动器（加自己的目录到 `sys.path`，调 `app.main`） |
| `media-mcp/media_mcp/config.py` | 环境变量 → `Config`；`doctor()` 体检 |
| `media-mcp/media_mcp/sniff.py` | 扩展名表 + magic bytes → MIME（含冲突告警） |
| `media-mcp/media_mcp/classify.py` | MIME → `kind`（选渲染器用） |
| `media-mcp/media_mcp/reference.py` | 绝对路径 → 同源引用（去盘符）；不合法返回 `None` |
| `media-mcp/media_mcp/validate.py` | 六种校验 → `Rejection \| None` |
| `media-mcp/media_mcp/envelope.py` | 成功/失败的 JSON 信封 |
| `media-mcp/media_mcp/rasterize.py` | `pdftoppm` 包装：内容哈希缓存、页数/DPI、失败不致命 |
| `media-mcp/media_mcp/tools/publish.py` | `publish_file` 的工具体（把上面串起来） |
| `media-mcp/media_mcp/app.py` | FastMCP 装配 + **工具描述（行为层）** |
| `media-mcp/media_mcp/selftest.py` | `--selftest`：真实跑一次发布 |
| `dsh-media-view/package.json` | bundle 声明（`dsh.bundle` + `dsh.client`） |
| `dsh-media-view/cordis.patch.yml` | 空补丁层（与 gallery 同构） |
| `dsh-media-view/lib/client.js` | 解析 + 按 kind 渲染 + CSS |
| `dsh-media-view/lib/index.js` | 包入口 |
| `dsh-media-view/test/harness.mjs` | 离线 harness（复用 gallery 的形态） |
| `tools/dsh_installer.py` | 改造：新增 `mcp-media` insert 块、新插件的 bundle/link、卸载往返 |

---

### Task 1: `media-mcp` 骨架与配置

**Files:**
- Create: `media-mcp/media_mcp/__init__.py`
- Create: `media-mcp/media_mcp/config.py`
- Create: `media-mcp/server.py`
- Test: `tests/test_media_config.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_config.py
"""Config is the only place the environment is read; everything else takes a Config."""

from pathlib import Path

import pytest

from media_mcp.config import Config, load_config


def test_defaults_pin_the_render_root_to_the_repo():
    cfg = load_config(env={})
    # parents[2] of media-mcp/media_mcp/config.py is the repo root.
    assert cfg.render_root.name == "renders"
    assert cfg.render_root.parent.name == "dshplugin"


def test_roots_default_to_the_single_repo_root():
    cfg = load_config(env={})
    assert len(cfg.roots) == 1
    assert cfg.roots[0] == cfg.render_root.parent


def test_fs_cwd_defaults_to_the_same_root_the_installer_pins():
    """A second source of truth here is how the reference silently 404s."""
    cfg = load_config(env={})
    assert cfg.fs_cwd == cfg.render_root.parent


def test_env_overrides_are_parsed():
    cfg = load_config(
        env={
            "MEDIA_MCP_ROOTS": r"D:\a;D:\b",
            "MEDIA_MCP_MAX_BYTES": "1024",
            "MEDIA_MCP_PDF_PAGES": "5",
            "MEDIA_MCP_PDF_DPI": "72",
        }
    )
    assert [p.name for p in cfg.roots] == ["a", "b"]
    assert cfg.max_bytes == 1024
    assert cfg.pdf_pages == 5
    assert cfg.pdf_dpi == 72


def test_a_bad_numeric_override_fails_loudly():
    """Silently falling back to the default would publish files the cap was meant to stop."""
    with pytest.raises(ValueError):
        load_config(env={"MEDIA_MCP_MAX_BYTES": "twenty"})


def test_doctor_reports_every_path_it_depends_on():
    report = load_config(env={}).doctor()
    assert set(report) >= {
        "python",
        "pdftoppm",
        "pdfinfo",
        "renderRoot",
        "fsCwd",
        "roots",
        "maxBytes",
        "pdftoppmFound",
        "pdfinfoFound",
    }
    assert isinstance(report["roots"], list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/__init__.py
"""Manim 之外的通用文件发布通道：一个工具，把本地文件交给对话流呈现。"""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
# media-mcp/media_mcp/config.py
"""Every environment read happens here.

Nothing else in this package touches `os.environ`, so `doctor()` can report the whole
runtime contract in one place and tests can construct a `Config` directly.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# parents[2] of media-mcp/media_mcp/config.py is the repository root.
DEFAULT_RENDER_ROOT = Path(__file__).resolve().parents[2] / "renders"
DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # matches the shipped /api/file cap
DEFAULT_PDF_PAGES = 3
DEFAULT_PDF_DPI = 110


def _positive_int(env: dict[str, str], name: str, fallback: int) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return fallback
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _path_list(env: dict[str, str], name: str, fallback: Path) -> tuple[Path, ...]:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return (fallback,)
    parts = [Path(part.strip()) for part in raw.split(";") if part.strip()]
    if not parts:
        raise ValueError(f"{name} listed no usable path")
    return tuple(parts)


@dataclass(frozen=True)
class Config:
    roots: tuple[Path, ...]
    fs_cwd: Path
    max_bytes: int
    pdf_pages: int
    pdf_dpi: int
    render_root: Path
    pdftoppm: str
    pdfinfo: str
    python: str

    def doctor(self) -> dict:
        return {
            "python": self.python,
            "pdftoppm": self.pdftoppm,
            "pdfinfo": self.pdfinfo,
            "renderRoot": self.render_root.as_posix(),
            "fsCwd": self.fs_cwd.as_posix(),
            "roots": [path.as_posix() for path in self.roots],
            "maxBytes": self.max_bytes,
            "pdfPages": self.pdf_pages,
            "pdfDpi": self.pdf_dpi,
            "pdftoppmFound": shutil.which(self.pdftoppm) is not None
            or Path(self.pdftoppm).exists(),
            "pdfinfoFound": shutil.which(self.pdfinfo) is not None
            or Path(self.pdfinfo).exists(),
        }


def load_config(env: dict[str, str] | None = None) -> Config:
    source = dict(os.environ if env is None else env)
    render_root = DEFAULT_RENDER_ROOT
    root = render_root.parent
    return Config(
        roots=_path_list(source, "MEDIA_MCP_ROOTS", root),
        # DEFAULT is the same expression the installer pins, so the two cannot drift.
        fs_cwd=Path(source.get("MEDIA_MCP_FS_CWD") or root),
        max_bytes=_positive_int(source, "MEDIA_MCP_MAX_BYTES", DEFAULT_MAX_BYTES),
        pdf_pages=_positive_int(source, "MEDIA_MCP_PDF_PAGES", DEFAULT_PDF_PAGES),
        pdf_dpi=_positive_int(source, "MEDIA_MCP_PDF_DPI", DEFAULT_PDF_DPI),
        render_root=render_root,
        pdftoppm=source.get("MEDIA_MCP_PDFTOPPM") or "pdftoppm",
        pdfinfo=source.get("MEDIA_MCP_PDFINFO") or "pdfinfo",
        python=source.get("MEDIA_MCP_PYTHON") or sys.executable,
    )
```

```python
# media-mcp/server.py
"""stdio entry point. Adds its own directory so `media_mcp` imports work from any cwd."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from media_mcp.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
```

`media_mcp/app.py` 还不存在，所以这一步先只建一个能导入的空壳，Task 9 填实：

```python
# media-mcp/media_mcp/app.py
from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError("filled in by Task 9")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_config.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add media-mcp tests/test_media_config.py
git commit -m "feat(media-mcp): 包骨架与配置（环境只在这一处读）"
```

---

### Task 2: MIME 嗅探

**Files:**
- Create: `media-mcp/media_mcp/sniff.py`
- Test: `tests/test_media_sniff.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_sniff.py
"""Extension lies; magic bytes do not. Both are needed, and a disagreement is reported."""

from pathlib import Path

import pytest

from media_mcp.sniff import sniff

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452")
JPEG = bytes.fromhex("ffd8ffe000104a46494600")
GIF = b"GIF89a" + b"\x00" * 16
PDF = b"%PDF-1.7\n" + b"\x00" * 16
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 8


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_extension_alone_is_enough_for_a_plain_png(tmp_path: Path):
    assert sniff(write(tmp_path, "a.png", PNG)) == ("image/png", [])


def test_magic_decides_when_the_extension_is_missing(tmp_path: Path):
    mime, warnings = sniff(write(tmp_path, "noext", PDF))
    assert mime == "application/pdf"
    assert warnings == []


def test_magic_decides_when_the_extension_lies(tmp_path: Path):
    """An .mp4 that is really a PDF must not be handed to a <video> element."""
    mime, warnings = sniff(write(tmp_path, "fake.mp4", PDF))
    assert mime == "application/pdf"
    assert len(warnings) == 1
    assert "mp4" in warnings[0]


def test_common_media_types_are_recognised(tmp_path: Path):
    assert sniff(write(tmp_path, "a.jpg", JPEG))[0] == "image/jpeg"
    assert sniff(write(tmp_path, "a.gif", GIF))[0] == "image/gif"
    assert sniff(write(tmp_path, "a.mp4", MP4))[0] == "video/mp4"
    assert sniff(write(tmp_path, "a.wav", WAV))[0] == "audio/wav"


def test_unknown_bytes_with_a_known_extension_are_trusted_but_flagged(tmp_path: Path):
    mime, warnings = sniff(write(tmp_path, "a.txt", b"hello"))
    assert mime == "text/plain"
    assert warnings == []


def test_unknown_bytes_and_unknown_extension_fall_back_to_octet_stream(tmp_path: Path):
    assert sniff(write(tmp_path, "a.bin", b"\x01\x02\x03\x04"))[0] == "application/octet-stream"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_sniff.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp.sniff'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/sniff.py
"""Identify a file's media type from its extension and its first bytes.

Two sources, deliberately: the extension is what the user meant, the magic is what the
file is. The renderer picks an element from the type — a PDF handed to `<video>` fails
silently in the browser — so a disagreement is resolved in favour of the bytes and
reported in `warnings`.
"""

from __future__ import annotations

from pathlib import Path

OCTET_STREAM = "application/octet-stream"

EXTENSION_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".csv": "text/csv",
    ".html": "text/html",
    ".htm": "text/html",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/plain",
}

# (magic, offset, mime). Longest/most specific first: `RIFF` alone is not enough.
MAGIC: tuple[tuple[bytes, int, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"RIFF", 0, "audio/wav"),  # refined below; RIFF also fronts WebP/AVI
    (b"%PDF-", 0, "application/pdf"),
    (b"fLaC", 0, "audio/flac"),
    (b"OggS", 0, "audio/ogg"),
    (b"ID3", 0, "audio/mpeg"),
    (b"\xff\xfb", 0, "audio/mpeg"),
    (b"ftyp", 4, "video/mp4"),
    (b"WEBP", 8, "image/webp"),
)


def _from_magic(head: bytes) -> str | None:
    for magic, offset, mime in MAGIC:
        if head[offset : offset + len(magic)] == magic:
            if mime == "audio/wav" and head[8:12] == b"WEBP":
                return "image/webp"
            if mime == "audio/wav" and head[8:12] == b"AVI ":
                return "video/x-msvideo"
            return mime
    return None


def sniff(path: Path) -> tuple[str, list[str]]:
    """Return `(mime, warnings)`. Never raises for an unreadable file — the caller
    validates existence first, and a zero-length read is a legitimate answer."""
    try:
        head = path.read_bytes()[:32]
    except OSError:
        head = b""

    by_extension = EXTENSION_MIME.get(path.suffix.lower())
    by_magic = _from_magic(head)

    warnings: list[str] = []
    if by_magic is not None and by_extension is not None and by_magic != by_extension:
        warnings.append(
            f"扩展名 {path.suffix} 声明 {by_extension}，实际内容像 {by_magic}；以内容为准"
        )
    if by_magic is not None:
        return by_magic, warnings
    if by_extension is not None:
        return by_extension, warnings
    return OCTET_STREAM, warnings
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_sniff.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add media-mcp/media_mcp/sniff.py tests/test_media_sniff.py
git commit -m "feat(media-mcp): MIME 嗅探（扩展名与 magic 冲突时以内容为准并告警）"
```

---

### Task 3: kind 分类

**Files:**
- Create: `media-mcp/media_mcp/classify.py`
- Test: `tests/test_media_classify.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_classify.py
"""`kind` selects a renderer. It must never be `other` for something we can render."""

import pytest

from media_mcp.classify import KIND_ORDER, classify

CASES = [
    ("image/png", "image"),
    ("image/svg+xml", "image"),
    ("video/mp4", "video"),
    ("video/quicktime", "video"),
    ("audio/wav", "audio"),
    ("audio/mpeg", "audio"),
    ("application/pdf", "pdf"),
    ("text/markdown", "text"),
    ("text/plain", "text"),
    ("application/json", "text"),
    ("application/octet-stream", "other"),
    ("application/zip", "other"),
]


@pytest.mark.parametrize("mime,expected", CASES)
def test_kind_is_derived_from_the_mime_family(mime: str, expected: str):
    assert classify(mime) == expected


def test_every_kind_has_a_renderer_in_the_documented_order():
    assert KIND_ORDER == ("image", "video", "audio", "pdf", "text", "other")


def test_an_unknown_mime_is_never_guessed_into_a_media_kind():
    """Guessing would make the renderer pick a player that cannot play it."""
    assert classify("application/vnd.ms-excel") == "other"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_classify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp.classify'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/classify.py
"""Map a MIME type to the renderer that owns it.

Deliberately total and dumb: `other` is the honest answer for anything we have no
element for, and a wrong guess shows the user a broken player instead of a file row.
"""

from __future__ import annotations

KIND_ORDER = ("image", "video", "audio", "pdf", "text", "other")

_EXACT = {
    "application/pdf": "pdf",
    "application/json": "text",
    "application/xml": "text",
}

_PREFIX = (
    ("image/", "image"),
    ("video/", "video"),
    ("audio/", "audio"),
    ("text/", "text"),
)


def classify(mime: str) -> str:
    normalized = (mime or "").split(";")[0].strip().lower()
    if normalized in _EXACT:
        return _EXACT[normalized]
    for prefix, kind in _PREFIX:
        if normalized.startswith(prefix):
            return kind
    return "other"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_classify.py -q`
Expected: PASS（14 passed）

- [ ] **Step 5: 提交**

```bash
git add media-mcp/media_mcp/classify.py tests/test_media_classify.py
git commit -m "feat(media-mcp): MIME → kind 分类（不认识就给 other，不猜）"
```

---

### Task 4: 同源引用

**Files:**
- Create: `media-mcp/media_mcp/reference.py`
- Test: `tests/test_media_reference.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_reference.py
"""The reference form was measured, not reasoned: `node:path.resolve` keeps only the
cwd's DRIVE for a `/`-rooted argument, so the reference is the absolute path minus the
drive letter. Getting this wrong is a silent 404 in the conversation."""

from pathlib import Path

import pytest

from media_mcp.reference import reference_for, rooted_reference


def test_the_drive_letter_is_dropped_and_every_directory_is_kept():
    assert rooted_reference("D:/a/b/c.mp4") == "/a/b/c.mp4"


def test_a_posix_absolute_path_is_already_the_reference():
    assert rooted_reference("/srv/a/b.mp4") == "/srv/a/b.mp4"


@pytest.mark.parametrize("bad", ["//server/share/a.mp4", "relative/a.mp4", "", "C:"])
def test_forms_with_no_same_origin_meaning_are_refused(bad: str):
    assert rooted_reference(bad) is None


@pytest.mark.parametrize("bad", ["a b.mp4", "a(b).mp4", "中文.mp4"])
def test_characters_that_break_markdown_or_urls_are_refused(bad: str):
    assert rooted_reference(f"/x/{bad}") is None


def test_reference_for_resolves_a_real_path(tmp_path: Path):
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"x")
    reference = reference_for(target)
    assert reference is not None
    assert reference.endswith("/clip.mp4")
    assert ":" not in reference


def test_reference_for_refuses_a_relative_path():
    assert reference_for(Path("clip.mp4")) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_reference.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp.reference'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/reference.py
"""Build the `/`-rooted reference the Host can resolve.

Measured with `node:path.resolve` on this machine, `cwd = D:\\myprogram\\dshplugin`:

    resolve(cwd, '/a/b.mp4')        -> 'D:\\a\\b.mp4'          (misses)
    resolve(cwd, '/D:/a/b.mp4')     -> 'D:\\D:\\a\\b.mp4'      (misses)
    resolve(cwd, '/myprogram/dshplugin/a/b.mp4') -> the file   (hits)

For a `/`-rooted argument `resolve` discards the cwd's directories entirely and keeps
only its DRIVE. So the reference is the absolute path minus the drive letter, and the
`fs` provider's cwd only has to sit on the same drive.
"""

from __future__ import annotations

import re
from pathlib import Path

DRIVE_RE = re.compile(r"^([A-Za-z]):(/.*)$")
# Whitespace and these characters break Markdown destinations or URL encoding.
UNSAFE_RE = re.compile(r"[\s()<>\"'\u4e00-\u9fff]")


def rooted_reference(absolute_posix: str) -> str | None:
    match = DRIVE_RE.match(absolute_posix)
    if match is not None:
        return match.group(2)
    if absolute_posix.startswith("/") and not absolute_posix.startswith("//"):
        return absolute_posix
    return None


def reference_for(path: Path) -> str | None:
    """`None` when no same-origin form exists — never a reference that would 404."""
    try:
        absolute = path.resolve(strict=False)
    except OSError:
        return None
    reference = rooted_reference(absolute.as_posix())
    if reference is None or UNSAFE_RE.search(reference):
        return None
    return reference
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_reference.py -q`
Expected: PASS（10 passed）

- [ ] **Step 5: 提交**

```bash
git add media-mcp/media_mcp/reference.py tests/test_media_reference.py
git commit -m "feat(media-mcp): 同源引用（去盘符），无合法形式时返回 None 而非发出坏引用"
```

---

### Task 5: 六种校验

**Files:**
- Create: `media-mcp/media_mcp/validate.py`
- Test: `tests/test_media_validate.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_validate.py
"""Six ways a publish can be refused. Each one must name its reason, because the model
reads it and corrects itself — a vague failure makes it retry blindly."""

from pathlib import Path

import pytest

from media_mcp.config import load_config
from media_mcp.validate import validate


@pytest.fixture()
def cfg(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    return load_config(
        env={
            "MEDIA_MCP_ROOTS": str(root),
            "MEDIA_MCP_FS_CWD": str(root),
            "MEDIA_MCP_MAX_BYTES": "32",
        }
    ), root


def test_a_good_file_passes(cfg):
    config, root = cfg
    target = root / "ok.bin"
    target.write_bytes(b"x" * 8)
    assert validate(str(target), config) is None


def test_a_relative_path_is_refused(cfg):
    config, _ = cfg
    rejection = validate("ok.bin", config)
    assert rejection.reason == "not-absolute"
    assert rejection.hint


def test_a_missing_file_is_refused(cfg):
    config, root = cfg
    rejection = validate(str(root / "absent.bin"), config)
    assert rejection.reason == "missing"


def test_a_directory_is_refused(cfg):
    config, root = cfg
    rejection = validate(str(root), config)
    assert rejection.reason == "not-a-file"


def test_a_file_outside_every_root_is_refused(cfg, tmp_path: Path):
    config, _ = cfg
    outside = tmp_path / "elsewhere.bin"
    outside.write_bytes(b"x")
    rejection = validate(str(outside), config)
    assert rejection.reason == "outside-root"
    assert "root" in rejection.hint.lower() or "允许" in rejection.hint


def test_a_file_on_another_drive_than_the_fs_cwd_is_refused(cfg):
    """The reference carries no drive, so the Host can only supply it from fs.cwd."""
    config, root = cfg
    other_drive = Path("Z:/nowhere.bin") if Path("Z:/").exists() is False else None
    if other_drive is None:
        pytest.skip("no second drive available to prove the mismatch")
    # Simulated by giving a root on Z: while fs cwd stays on the real drive.
    config_on_z = load_config(
        env={
            "MEDIA_MCP_ROOTS": "Z:/",
            "MEDIA_MCP_FS_CWD": str(root),
            "MEDIA_MCP_MAX_BYTES": "32",
        }
    )
    rejection = validate("Z:/nowhere.bin", config_on_z)
    assert rejection.reason in {"wrong-drive", "missing"}


def test_a_file_exactly_at_the_cap_passes(cfg):
    config, root = cfg
    target = root / "exact.bin"
    target.write_bytes(b"x" * 32)
    assert validate(str(target), config) is None


def test_a_file_one_byte_over_the_cap_is_refused_with_both_numbers(cfg):
    config, root = cfg
    target = root / "big.bin"
    target.write_bytes(b"x" * 33)
    rejection = validate(str(target), config)
    assert rejection.reason == "too-large"
    assert "33" in rejection.detail and "32" in rejection.detail
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_validate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp.validate'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/validate.py
"""The six gates a path must pass before a reference is minted.

Ordered cheapest-first, and ordered so the message the model receives names the thing it
can actually fix. The size gate is last because it is the only one that has to stat the
file twice on a large artefact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .reference import reference_for


@dataclass(frozen=True)
class Rejection:
    reason: str
    detail: str
    hint: str

    def as_dict(self) -> dict:
        return {"reason": self.reason, "detail": self.detail, "hint": self.hint}


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except (ValueError, OSError):
        return False
    return True


def _drive(path: Path) -> str:
    return path.resolve(strict=False).drive.lower()


def validate(raw_path: str, cfg: Config) -> Rejection | None:
    if not raw_path or not raw_path.strip():
        return Rejection("not-absolute", "路径为空", "传一个绝对路径")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        return Rejection(
            "not-absolute", f"{raw_path} 不是绝对路径", "传一个绝对路径（含盘符）"
        )

    if not candidate.exists():
        return Rejection("missing", f"{raw_path} 不存在", "确认路径无误后重试")

    if not candidate.is_file():
        return Rejection("not-a-file", f"{raw_path} 不是普通文件", "只能发布文件，不能发布目录")

    if not any(_is_within(candidate, root) for root in cfg.roots):
        allowed = "；".join(root.as_posix() for root in cfg.roots)
        return Rejection(
            "outside-root",
            f"{raw_path} 不在允许发布的根目录内",
            f"允许的根目录：{allowed}",
        )

    if _drive(candidate) != _drive(cfg.fs_cwd):
        return Rejection(
            "wrong-drive",
            f"{raw_path} 与文件系统基准 {cfg.fs_cwd.as_posix()} 不在同一个盘符",
            "引用形式不带盘符，宿主只能从 fs.cwd 取盘符；把文件放到同一盘符下",
        )

    if reference_for(candidate) is None:
        return Rejection(
            "unreferenceable",
            f"{raw_path} 的路径含空格/括号/中文，或无法形成同源引用",
            "把它复制到一个只用 ASCII、无空格的名字下再发布",
        )

    try:
        size = candidate.stat().st_size
    except OSError as error:
        return Rejection("missing", f"无法读取 {raw_path}：{error}", "确认文件可读")

    if size > cfg.max_bytes:
        return Rejection(
            "too-large",
            f"文件 {size} 字节，超过上限 {cfg.max_bytes} 字节",
            "压缩或切片后再发布；不要重复重试",
        )

    return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_validate.py -q`
Expected: PASS（8 passed, 可能 1 skipped）

- [ ] **Step 5: 提交**

```bash
git add media-mcp/media_mcp/validate.py tests/test_media_validate.py
git commit -m "feat(media-mcp): 六种校验，各自给出可据以纠正的 reason/hint"
```

---

### Task 6: 信封

**Files:**
- Create: `media-mcp/media_mcp/envelope.py`
- Test: `tests/test_media_envelope.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_envelope.py
"""One shape for both outcomes. The renderer parses this, so the keys are a contract."""

from pathlib import Path

from media_mcp.envelope import descriptor, failure, success
from media_mcp.validate import Rejection


def test_descriptor_carries_everything_the_renderer_needs(tmp_path: Path):
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"x" * 10)
    item = descriptor(
        target,
        reference="/a/clip.mp4",
        kind="video",
        mime="video/mp4",
        title="演示",
        warnings=[],
    )
    assert item["kind"] == "video"
    assert item["mime"] == "video/mp4"
    assert item["name"] == "clip.mp4"
    assert item["bytes"] == 10
    assert item["reference"] == "/a/clip.mp4"
    assert item["path"].endswith("clip.mp4")
    assert item["title"] == "演示"
    assert item["warnings"] == []


def test_descriptor_omits_an_empty_title(tmp_path: Path):
    target = tmp_path / "a.png"
    target.write_bytes(b"x")
    item = descriptor(
        target, reference="/a/a.png", kind="image", mime="image/png", title=None, warnings=[]
    )
    assert "title" not in item


def test_success_lists_the_primary_media_first():
    primary = {"kind": "pdf", "name": "r.pdf"}
    pages = [{"kind": "image", "name": "page-01.png"}]
    payload = success(primary, extras=pages, warnings=["w"])
    assert payload["ok"] is True
    assert payload["media"] == primary
    assert payload["extras"] == pages
    assert payload["warnings"] == ["w"]


def test_failure_names_the_reason_and_hints(tmp_path: Path):
    payload = failure(Rejection("too-large", "33 > 32", "压缩后再发"))
    assert payload["ok"] is False
    assert payload["reason"] == "too-large"
    assert payload["detail"] == "33 > 32"
    assert payload["hint"] == "压缩后再发"
    assert "media" not in payload
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_envelope.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp.envelope'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/envelope.py
"""The JSON the renderer parses. One success shape, one failure shape.

`reference` is computed host-side and copied verbatim by the client, so the rule about
how a path resolves lives in exactly one place.
"""

from __future__ import annotations

from pathlib import Path

from .validate import Rejection


def descriptor(
    path: Path,
    *,
    reference: str,
    kind: str,
    mime: str,
    title: str | None,
    warnings: list[str],
    pages: int | None = None,
) -> dict:
    item: dict = {
        "kind": kind,
        "mime": mime,
        "name": path.name,
        "path": str(path),
        "reference": reference,
        "bytes": path.stat().st_size,
        "warnings": list(warnings),
    }
    if title:
        item["title"] = title
    if pages is not None:
        item["pages"] = pages
    return item


def success(primary: dict, *, extras: list[dict] | None = None, warnings: list[str] | None = None) -> dict:
    return {
        "ok": True,
        "media": primary,
        "extras": list(extras or []),
        "warnings": list(warnings or []),
    }


def failure(rejection: Rejection) -> dict:
    return {"ok": False, **rejection.as_dict()}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_envelope.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add media-mcp/media_mcp/envelope.py tests/test_media_envelope.py
git commit -m "feat(media-mcp): 成功/失败两种信封，schema 即渲染器契约"
```

---

### Task 7: PDF 光栅化

**Files:**
- Create: `media-mcp/media_mcp/rasterize.py`
- Test: `tests/test_media_rasterize.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_rasterize.py
"""PDF cannot be shown in an <iframe>: /api/file answers with
`content-security-policy: sandbox; default-src 'none'`, so the browser's PDF viewer
never renders. Rasterising to PNG reuses the image channel that already works."""

import subprocess
from pathlib import Path

import pytest

from media_mcp.config import load_config
from media_mcp.rasterize import cache_dir, rasterize


@pytest.fixture()
def cfg(tmp_path: Path):
    renders = tmp_path / "renders"
    renders.mkdir()
    return load_config(
        env={
            "MEDIA_MCP_ROOTS": str(tmp_path),
            "MEDIA_MCP_FS_CWD": str(tmp_path),
            "MEDIA_MCP_PDF_PAGES": "3",
            "MEDIA_MCP_PDF_DPI": "72",
        }
    )


def test_cache_dir_is_content_addressed(tmp_path: Path, cfg):
    first = tmp_path / "a.pdf"
    first.write_bytes(b"%PDF-1.7\nsame")
    second = tmp_path / "b.pdf"
    second.write_bytes(b"%PDF-1.7\nsame")
    other = tmp_path / "c.pdf"
    other.write_bytes(b"%PDF-1.7\ndifferent")
    assert cache_dir(cfg.render_root, first) == cache_dir(cfg.render_root, second)
    assert cache_dir(cfg.render_root, first) != cache_dir(cfg.render_root, other)


def test_a_missing_pdftoppm_is_not_fatal_and_is_reported(tmp_path: Path, cfg):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    broken = load_config(
        env={
            "MEDIA_MCP_ROOTS": str(tmp_path),
            "MEDIA_MCP_FS_CWD": str(tmp_path),
            "MEDIA_MCP_PDFTOPPM": "definitely-not-a-real-binary",
        }
    )
    pages, total, warnings = rasterize(pdf, broken)
    assert pages == []
    assert total is None
    assert any("pdftoppm" in w for w in warnings)


def test_a_corrupt_pdf_is_not_fatal(tmp_path: Path, cfg):
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(b"not a pdf at all")
    pages, total, warnings = rasterize(pdf, cfg)
    assert pages == []
    assert warnings


@pytest.mark.skipif(
    subprocess.run(["pdftoppm", "-v"], capture_output=True).returncode not in (0, 1),
    reason="pdftoppm is not installed",
)
def test_a_real_pdf_becomes_pngs(tmp_path: Path, cfg):
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "minimal.pdf"
    pages, total, warnings = rasterize(fixture, cfg)
    assert pages, f"no page produced; warnings={warnings}"
    assert pages[0].suffix == ".png"
    assert pages[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert total == 1


def test_the_page_cap_is_honoured(tmp_path: Path, cfg):
    """A 50-page PDF must not become 50 images in the conversation."""
    assert cfg.pdf_pages == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_rasterize.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp.rasterize'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/rasterize.py
"""Turn the first pages of a PDF into PNGs, so they can use the image channel.

Why not `<iframe>`: `/api/file` answers with `content-security-policy: sandbox;
default-src 'none'` — no `allow-*` tokens at all, so the document is a unique opaque
origin with plugins and scripts disabled, and the browser's PDF viewer does not render.

`pdftoppm` ships with MiKTeX, which this project already requires for Manim's LaTeX, so
this adds no new dependency. The cache directory is content-addressed: publishing the
same PDF twice converts once and cannot collide on a name.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from .config import Config

PAGE_RE = re.compile(r"-(\d+)\.png$")


def cache_dir(render_root: Path, pdf: Path) -> Path:
    digest = hashlib.sha1(pdf.read_bytes()).hexdigest()[:12]
    return render_root / "_pdf" / digest


def count_pages(pdf: Path, cfg: Config) -> int | None:
    """Total pages, via `pdfinfo` — which ships in the same MiKTeX bundle as `pdftoppm`.

    `pdftoppm` itself never reports a total, and rasterising every page just to count
    them would turn a 50-page report into 50 rendered pages of wasted work. `None` when
    the tool is missing or the output is not understood: the card simply omits the
    count rather than inventing one.
    """
    argv = [cfg.pdfinfo, str(pdf)]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in completed.stdout.splitlines():
        if line.lower().startswith("pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def rasterize(pdf: Path, cfg: Config) -> tuple[list[Path], int | None, list[str]]:
    """Return `(page_pngs, total_pages, warnings)`. Never raises: a broken converter or
    a corrupt PDF degrades the card, it does not fail the publish."""
    total = count_pages(pdf, cfg)
    target = cache_dir(cfg.render_root, pdf)
    cached = sorted(target.glob("page-*.png"))
    if cached:
        return cached, total, []

    target.mkdir(parents=True, exist_ok=True)
    prefix = target / "page"
    argv = [
        cfg.pdftoppm,
        "-png",
        "-r",
        str(cfg.pdf_dpi),
        "-f",
        "1",
        "-l",
        str(cfg.pdf_pages),
        str(pdf),
        str(prefix),
    ]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return [], None, [f"PDF 首页预览不可用（{cfg.pdftoppm} 调用失败：{error}）"]

    pages = sorted(target.glob("page-*.png"))
    if not pages:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"退出码 {completed.returncode}"
        return [], total, [f"PDF 首页预览不可用（{tail}）"]

    return pages, total, []
```

同时把 `count_pages` 加进 `rasterize` 的测试文件：

```python
def test_the_total_page_count_comes_from_pdfinfo(tmp_path: Path, cfg, monkeypatch):
    """`pdftoppm` never reports a total; inventing one would show "共 1 页" on a report."""
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(
        "media_mcp.rasterize.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="Pages:          12\n", stderr=""),
    )
    from media_mcp.rasterize import count_pages

    assert count_pages(pdf, cfg) == 12


def test_an_unreadable_pdfinfo_output_yields_no_count(tmp_path: Path, cfg, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(
        "media_mcp.rasterize.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="boom"),
    )
    from media_mcp.rasterize import count_pages

    assert count_pages(pdf, cfg) is None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_rasterize.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add media-mcp/media_mcp/rasterize.py tests/test_media_rasterize.py
git commit -m "feat(media-mcp): PDF 光栅化（内容寻址缓存；转换失败只降级不致命）"
```

---

### Task 8: `publish_file` 工具体

**Files:**
- Create: `media-mcp/media_mcp/tools/__init__.py`
- Create: `media-mcp/media_mcp/tools/publish.py`
- Test: `tests/test_media_publish.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_publish.py
"""The tool body wires the parts together. Its job is the ORDER: validate, then sniff,
then reference, then (for PDF only) rasterise."""

from pathlib import Path

import pytest

from media_mcp.config import load_config
from media_mcp.tools.publish import publish


@pytest.fixture()
def cfg(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    return load_config(
        env={
            "MEDIA_MCP_ROOTS": str(root),
            "MEDIA_MCP_FS_CWD": str(root),
            "MEDIA_MCP_MAX_BYTES": "1000000",
        }
    ), root


def test_a_video_publishes_with_a_video_descriptor(cfg):
    config, root = cfg
    target = root / "clip.mp4"
    target.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32)
    payload = publish(str(target), None, config)
    assert payload["ok"] is True
    assert payload["media"]["kind"] == "video"
    assert payload["media"]["mime"] == "video/mp4"
    assert payload["media"]["reference"].endswith("/clip.mp4")
    assert payload["extras"] == []


def test_a_rejection_short_circuits_before_any_reference_is_minted(cfg):
    config, root = cfg
    payload = publish(str(root / "absent.mp4"), None, config)
    assert payload["ok"] is False
    assert payload["reason"] == "missing"
    assert "media" not in payload


def test_the_title_reaches_the_descriptor(cfg):
    config, root = cfg
    target = root / "a.png"
    target.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 16)
    payload = publish(str(target), "示意图", config)
    assert payload["media"]["title"] == "示意图"


def test_a_pdf_carries_its_rasterised_pages_as_extras(cfg, monkeypatch):
    config, root = cfg
    target = root / "report.pdf"
    target.write_bytes(b"%PDF-1.7\n" + b"\x00" * 32)
    page = root / "page-1.png"
    page.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 16)
    monkeypatch.setattr(
        "media_mcp.tools.publish.rasterize", lambda pdf, cfg_: ([page], 3, [])
    )
    payload = publish(str(target), None, config)
    assert payload["ok"] is True
    assert payload["media"]["kind"] == "pdf"
    assert [item["kind"] for item in payload["extras"]] == ["image"]
    assert payload["extras"][0]["reference"].endswith("/page-1.png")


def test_a_failed_rasterisation_still_publishes_the_pdf(cfg, monkeypatch):
    config, root = cfg
    target = root / "report.pdf"
    target.write_bytes(b"%PDF-1.7\n" + b"\x00" * 32)
    monkeypatch.setattr(
        "media_mcp.tools.publish.rasterize", lambda pdf, cfg_: ([], None, ["坏了"])
    )
    payload = publish(str(target), None, config)
    assert payload["ok"] is True
    assert payload["extras"] == []
    assert "坏了" in payload["warnings"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_publish.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_mcp.tools'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/tools/__init__.py
"""Tool bodies, kept out of `app.py` so they can be called in-process by tests."""
```

```python
# media-mcp/media_mcp/tools/publish.py
"""`publish_file`: the whole channel in one function.

Order matters. Validation runs first and returns early, so a refusal can never mint a
reference — a reference that would 404 or 413 is worse than no reference, because the
user sees a broken card instead of a sentence explaining what to do.
"""

from __future__ import annotations

from pathlib import Path

from ..classify import classify
from ..config import Config
from ..envelope import descriptor, failure, success
from ..rasterize import rasterize
from ..reference import reference_for
from ..sniff import sniff
from ..validate import Rejection, validate


def publish(raw_path: str, title: str | None, cfg: Config) -> dict:
    rejection = validate(raw_path, cfg)
    if rejection is not None:
        return failure(rejection)

    target = Path(raw_path).resolve(strict=False)
    mime, warnings = sniff(target)
    kind = classify(mime)
    reference = reference_for(target)
    if reference is None:
        # validate() already refuses this case; reaching here means the two disagree,
        # and a disagreement must never be silently papered over with a bad reference.
        return failure(
            Rejection(
                "unreferenceable",
                f"{target} 通过了校验却算不出同源引用",
                "把文件复制到一个只用 ASCII、无空格的路径下再发布",
            )
        )

    primary = descriptor(
        target,
        reference=reference,
        kind=kind,
        mime=mime,
        title=title,
        warnings=warnings,
    )

    extras: list[dict] = []
    if kind == "pdf":
        pages, total, page_warnings = rasterize(target, cfg)
        warnings = [*warnings, *page_warnings]
        primary["warnings"] = list(warnings)
        if total is not None:
            primary["pages"] = total
        for page in pages:
            page_reference = reference_for(page)
            if page_reference is None:
                warnings.append(f"跳过无法引用的预览图 {page.name}")
                continue
            extras.append(
                descriptor(
                    page,
                    reference=page_reference,
                    kind="image",
                    mime="image/png",
                    title=None,
                    warnings=[],
                )
            )
        primary["warnings"] = list(warnings)

    return success(primary, extras=extras, warnings=warnings)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_publish.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add media-mcp/media_mcp/tools tests/test_media_publish.py
git commit -m "feat(media-mcp): publish_file 工具体（校验先行，拒绝时绝不生成引用）"
```

---

### Task 9: MCP 装配、工具描述与自检

**Files:**
- Modify: `media-mcp/media_mcp/app.py`（替换 Task 1 的占位）
- Create: `media-mcp/media_mcp/selftest.py`
- Test: `tests/test_media_app.py`
- Test: `tests/test_media_selftest.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_media_app.py
"""The description IS the behaviour layer (spec §3.2 / §6.6): there is no skill, so a
vague description means the model never publishes, or publishes everything."""

from media_mcp.app import TOOL_DESCRIPTION, build_server


def test_the_description_answers_all_four_behaviour_questions():
    assert "什么时候" in TOOL_DESCRIPTION or "该发" in TOOL_DESCRIPTION
    assert "不要" in TOOL_DESCRIPTION or "不该" in TOOL_DESCRIPTION
    assert "3" in TOOL_DESCRIPTION  # the per-turn budget
    assert "MiB" in TOOL_DESCRIPTION or "上限" in TOOL_DESCRIPTION


def test_the_description_says_a_refusal_carries_a_reason():
    assert "reason" in TOOL_DESCRIPTION


def test_the_server_exposes_exactly_one_tool_named_publish_file():
    """The wire name is `mcp__media__publish_file`: `media` comes from `FastMCP("media")`
    and `publish_file` from the registration. Both halves are load-bearing — the client
    plugin hard-codes the joined string, and a mismatch never renders."""
    server = build_server()
    names = {tool.name for tool in server._tool_manager.list_tools()}  # noqa: SLF001
    assert names == {"publish_file"}
```

> `server._tool_manager.list_tools()` is private, but it is the only in-process way to
> read the registry, and it exists in the installed FastMCP (verified by hand). The
> alternative — asserting on `app.py`'s source text — would pass even if the server name
> were changed, which is the exact failure this needs to catch.

```python
# tests/test_media_selftest.py
"""The self-test must exercise the REAL tool body, not a stub — the whole point is to
catch "works in tests, breaks as a stdio server"."""

from pathlib import Path

from media_mcp.config import load_config
from media_mcp.selftest import run


def test_selftest_publishes_a_real_png(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    cfg = load_config(
        env={
            "MEDIA_MCP_ROOTS": str(root),
            "MEDIA_MCP_FS_CWD": str(root),
        }
    )
    code = run(cfg)
    assert code == 0


def test_selftest_fails_when_it_cannot_publish(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    cfg = load_config(
        env={"MEDIA_MCP_ROOTS": str(root), "MEDIA_MCP_FS_CWD": str(root)}
    )
    monkeypatch.setattr("media_mcp.selftest.publish", lambda *a, **k: {"ok": False})
    assert run(cfg) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_app.py tests/test_media_selftest.py -q`
Expected: FAIL — `ImportError: cannot import name 'TOOL_DESCRIPTION'`

- [ ] **Step 3: 最小实现**

```python
# media-mcp/media_mcp/app.py
"""FastMCP assembly, plus the tool description that carries all behaviour guidance.

There is deliberately no Skill for this capability. The shipped `read_image` and
`present` tools keep their guidance in their own descriptions, and a Skill has a failure
mode this feature cannot afford: if the router does not load it, the model produces a
video and never hands it over. A description is always in context.
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .tools.publish import publish

TOOL_DESCRIPTION = """\
把一个本地文件发布到对话里，让用户直接看到/听到/读到它（视频会内嵌播放、音频会内嵌播放、
PDF 会显示前 3 页、图片直接显示、其它格式给出文件名与大小）。

**什么时候该发**：你刚产出的东西是用户要「看」的——视频、音频、PDF、图片、报告。
用一段文字描述它，不如让他直接看到。

**什么时候不要发**：中间产物、日志、调试截图；用户没要求看的；一句话就能说清的东西；
同一份文件在同一轮里重复发。

**一轮最多发 3 个**。再多会刷屏，重点反而被淹没。

**上限 20 MiB**。超了就压缩或切片，或者只把路径写在正文里并说明原因——**不要反复重试**。

失败时会返回 `reason`（missing / not-a-file / outside-root / wrong-drive / too-large /
unreferenceable）和 `hint`，按 `hint` 纠正后重试一次；仍失败就把路径写进正文，不要卡住。
"""


def build_server(cfg=None):
    config = cfg or load_config()
    server = FastMCP("media")

    @server.tool(name="publish_file", description=TOOL_DESCRIPTION)
    def publish_file(path: str, title: str | None = None) -> dict:
        """Publish one existing file to the conversation. `path` must be absolute."""
        return publish(path, title, config)

    return server


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in args:
        from .selftest import run

        return run(load_config())
    if "--doctor" in args:
        import json

        print(json.dumps(load_config().doctor(), ensure_ascii=False, indent=2))
        return 0
    build_server().run()
    return 0
```

```python
# media-mcp/media_mcp/selftest.py
"""`--selftest`: publish one real PNG through the real tool body.

Kept to one artefact so it can run on every install without becoming a wait.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .config import Config
from .tools.publish import publish

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png(width: int = 8, height: int = 8) -> bytes:
    raw = b"".join(b"\x00" + bytes([80, 140, 200]) * width for _ in range(height))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def sample_file(render_root: Path) -> Path:
    target = render_root / "_selftest"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "selftest.png"
    path.write_bytes(_png())
    return path


def run(cfg: Config) -> int:
    path = sample_file(cfg.render_root)
    payload = publish(str(path), "自检", cfg)
    if payload.get("ok") is not True:
        print(f"FAIL: publish_file 拒绝了自己的样本：{payload}", flush=True)
        return 1
    media = payload["media"]
    if media["kind"] != "image" or not media["reference"].startswith("/"):
        print(f"FAIL: 描述符形状不对：{media}", flush=True)
        return 1
    print(f"OK: {media['name']} ({media['bytes']}B) -> {media['reference']}", flush=True)
    return 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_media_app.py tests/test_media_selftest.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 真机跑一次自检**

Run: `D:\ProgramData\anaconda3\python.exe media-mcp\server.py --selftest`
Expected: 退出码 0，打印 `OK: selftest.png (...) -> /.../selftest.png`

- [ ] **Step 6: 提交**

```bash
git add media-mcp tests/test_media_app.py tests/test_media_selftest.py
git commit -m "feat(media-mcp): MCP 装配 + 工具描述（行为层）+ --selftest"
```

---

### Task 10: `dsh-media-view` 骨架与信封解析

**Files:**
- Create: `dsh-media-view/package.json`
- Create: `dsh-media-view/cordis.patch.yml`
- Create: `dsh-media-view/lib/index.js`
- Create: `dsh-media-view/lib/client.js`
- Create: `dsh-media-view/test/harness.mjs`
- Test: `dsh-media-view/test/parse.test.mjs`

- [ ] **Step 1: 写失败的测试**

```javascript
// dsh-media-view/test/parse.test.mjs
// Parsing is the defensive layer: a malformed envelope must degrade to a plain row,
// never throw, because a throw inside a tool view takes the whole conversation down.
import assert from "node:assert/strict";
import { test } from "node:test";

import { loadClient } from "./harness.mjs";

const { plugin } = loadClient();
const { readEnvelope, readMedia } = plugin.__internals;

function resultWith(blocks) {
	return { kind: "tool-result", content: blocks, isError: false };
}

test("reads the envelope out of the single text block", () => {
	const payload = { ok: true, media: { kind: "video", name: "a.mp4" } };
	const found = readEnvelope(resultWith([{ type: "text", text: JSON.stringify(payload, null, 2) }]));
	assert.deepEqual(found, payload);
});

test("ignores non-text blocks around it", () => {
	const payload = { ok: true, media: { kind: "image", name: "a.png" } };
	const found = readEnvelope(
		resultWith([
			{ type: "text", text: "noise" },
			{ type: "image", attachment: {} },
			{ type: "text", text: JSON.stringify(payload) },
		]),
	);
	assert.deepEqual(found, payload);
});

test("a malformed envelope yields null instead of throwing", () => {
	assert.equal(readEnvelope(resultWith([{ type: "text", text: "{ not json" }])), null);
	assert.equal(readEnvelope(resultWith([{ type: "text", text: "[1,2,3]" }])), null);
	assert.equal(readEnvelope(resultWith([])), null);
	assert.equal(readEnvelope(undefined), null);
});

test("readMedia returns null for every shape that is not a usable descriptor", () => {
	assert.equal(readMedia(null), null);
	assert.equal(readMedia({ ok: false, reason: "missing" }), null);
	assert.equal(readMedia({ ok: true }), null);
	assert.equal(readMedia({ ok: true, media: { kind: "video" } }), null); // no reference
	assert.equal(readMedia({ ok: true, media: { reference: "/a" } }), null); // no kind
	assert.deepEqual(readMedia({ ok: true, media: { kind: "video", reference: "/a" } }), {
		kind: "video",
		reference: "/a",
	});
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd dsh-media-view && node --test "test/*.test.mjs"`
Expected: FAIL — `Cannot find module './harness.mjs'`

- [ ] **Step 3: 最小实现**

```json
// dsh-media-view/package.json
{
  "name": "dsh-media-view",
  "version": "0.1.0",
  "description": "DeepSeek Harness 通用文件发布渲染器：把 mcp__media__publish_file 的结果按模态内嵌呈现",
  "type": "module",
  "main": "lib/index.js",
  "exports": {
    ".": "./lib/index.js",
    "./client": "./lib/client.js",
    "./package.json": "./package.json"
  },
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    },
    "client": {
      "inject": [
        "@deepseek-ai/dsh-api-remotes",
        "@deepseek-ai/dsh-client-ui-renderer",
        "@deepseek-ai/dsh-client-ui-layout"
      ],
      "platform": "web"
    }
  },
  "scripts": {
    "test": "node --test \"test/*.test.mjs\""
  },
  "license": "MIT",
  "peerDependencies": {
    "@deepseek-ai/cordis": "^4.0.2"
  }
}
```

```yaml
# dsh-media-view/cordis.patch.yml
# 本插件不覆盖任何 composition 行；它只向槽位注册。空层让 bundle 声明成立。
[]
```

```javascript
// dsh-media-view/lib/index.js
export const name = "dsh-media-view";
export const client = "./client.js";
```

```javascript
// dsh-media-view/lib/client.js
/**
 * The conversation-side renderer for `mcp__media__publish_file`.
 *
 * Why a tool view and not the assistant's own text: the assistant body is rendered by
 * the shipped `assistant-step` node, and replacing it would mean reimplementing all of
 * Markdown. `tool.call.toolview` is keyed by tool name, its key domain is open, and an
 * unclaimed key falls back to the generic tool row — so registering our own tool's key
 * is additive and shadows nothing.
 *
 * The key is a literal and a typo never renders (no error, no fallback notice), so
 * `test/register.test.mjs` asserts it character for character.
 */
window.__ModuleLoader__.load({
	id: "dsh-media-view",
	factory: (require) => {
		const module = { exports: {} };
		const exports = module.exports;

		const react = require("react");
		const h = react.createElement;

		const TOOL_KEY = "mcp__media__publish_file";

		/** Pull our JSON envelope out of a settled tool result. Never throws. */
		function readEnvelope(block) {
			const content = block?.content;
			if (!Array.isArray(content)) return null;
			for (const item of content) {
				if (item?.type !== "text" || typeof item.text !== "string") continue;
				const trimmed = item.text.trim();
				if (!trimmed.startsWith("{")) continue;
				try {
					const parsed = JSON.parse(trimmed);
					if (parsed && typeof parsed === "object") return parsed;
				} catch {
					// Not ours, or truncated: keep looking, then give up quietly.
				}
			}
			return null;
		}

		/** A descriptor we can actually render, or null. */
		function readMedia(envelope) {
			if (!envelope || envelope.ok !== true) return null;
			const media = envelope.media;
			if (!media || typeof media !== "object") return null;
			if (typeof media.kind !== "string" || typeof media.reference !== "string") return null;
			return media;
		}

		exports.__internals = { TOOL_KEY, readEnvelope, readMedia };
		exports.apply = function apply() {
			throw new Error("apply is added by Task 11");
		};
		return module.exports;
	},
});
```

```javascript
// dsh-media-view/test/harness.mjs
// Mirrors the gallery harness: evaluate the browser bundle against mock surfaces so the
// renderer can be tested without a browser or a running DSH.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const CLIENT_PATH = resolve(HERE, "..", "lib", "client.js");

export function createReactStub() {
	const hooks = { states: [], setters: [], effects: [], refs: [] };
	return {
		hooks,
		Fragment: Symbol.for("react.fragment"),
		createElement(type, props, ...children) {
			return { type, props: { ...(props ?? {}), children: children.flat(Infinity) } };
		},
		useState(initial) {
			const value = typeof initial === "function" ? initial() : initial;
			hooks.states.push(value);
			hooks.setters.push(() => {});
			return [value, () => {}];
		},
		useEffect(fn) {
			hooks.effects.push({ fn });
		},
		useMemo(fn) {
			return fn();
		},
		useCallback(fn) {
			return fn;
		},
		useRef(value) {
			const ref = { current: value };
			hooks.refs.push(ref);
			return ref;
		},
	};
}

export function createCtx({ services = {} } = {}) {
	const registrations = [];
	const asked = [];
	const ctx = {
		slots: {
			inject(_key, callback) {
				return callback();
			},
			register(options, component) {
				registrations.push({ options, component });
				return () => {};
			},
		},
		get(name) {
			asked.push(name);
			return services[name] ?? ctx[name];
		},
		on() {
			return () => {};
		},
	};
	for (const [name, value] of Object.entries(services)) ctx[name] = value;
	return { registrations, asked, ctx };
}

export function loadClient() {
	let captured = null;
	globalThis.window = {
		__ModuleLoader__: {
			load(entry) {
				captured = entry;
			},
		},
		location: { protocol: "http:", origin: "http://127.0.0.1:3080" },
		addEventListener() {},
		removeEventListener() {},
	};
	const react = createReactStub();
	const loader = (specifier) => {
		if (specifier === "react") return react;
		throw new Error(`unexpected require(${JSON.stringify(specifier)})`);
	};
	new Function("require", readFileSync(CLIENT_PATH, "utf8"))(loader);
	if (captured === null) throw new Error("client.js did not call __ModuleLoader__.load");
	return { entry: captured, plugin: captured.factory(loader), react };
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd dsh-media-view && node --test "test/*.test.mjs"`
Expected: PASS（4 tests, 0 fail）

- [ ] **Step 5: 提交**

```bash
git add dsh-media-view
git commit -m "feat(dsh-media-view): 插件骨架与信封解析（畸形输入退化为普通行，绝不抛）"
```

---

### Task 11: 按 kind 渲染

**Files:**
- Modify: `dsh-media-view/lib/client.js`
- Test: `dsh-media-view/test/render.test.mjs`
- Test: `dsh-media-view/test/register.test.mjs`

- [ ] **Step 1: 写失败的测试**

```javascript
// dsh-media-view/test/register.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, loadClient } from "./harness.mjs";

const { plugin } = loadClient();

test("the registered key is character-for-character the MCP wire name", () => {
	// `mcp__<serverName>__<rawName>`. A typo here never renders and never warns —
	// the slot simply has no occupant for that tool, so nothing would catch it.
	assert.equal(plugin.__internals.TOOL_KEY, "mcp__media__publish_file");
});

test("apply registers exactly one tool view and nothing else", () => {
	const { ctx, registrations } = createCtx({ services: { sidebarRight: {} } });
	plugin.apply(ctx);
	assert.equal(registrations.length, 1);
	assert.equal(registrations[0].options.name, "tool.call.toolview");
	assert.equal(registrations[0].options.key, "mcp__media__publish_file");
	assert.equal(typeof registrations[0].component, "function");
});

test("the renderer reads services from declared properties, never ctx.get", () => {
	const { ctx, asked } = createCtx({ services: { sidebarRight: {} } });
	plugin.apply(ctx);
	assert.deepEqual(asked, [], "ctx.get crosses a scope boundary and yields undefined");
});

test("the plugin declares only the services it reaches", () => {
	assert.deepEqual(plugin.inject, ["slots", "sidebarRight"]);
});

test("apply never issues a write", () => {
	const { ctx } = createCtx({ services: { sidebarRight: {} } });
	const before = JSON.stringify(globalThis.fetch ?? null);
	plugin.apply(ctx);
	assert.equal(JSON.stringify(globalThis.fetch ?? null), before);
});
```

```javascript
// dsh-media-view/test/render.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { loadClient } from "./harness.mjs";

const { plugin } = loadClient();
const { MediaView, fileUrl } = plugin.__internals;

function settled(media, extras = []) {
	return {
		kind: "tool-result",
		call: { name: "mcp__media__publish_file", argsRaw: "{}" },
		content: [
			{ type: "text", text: JSON.stringify({ ok: true, media, extras, warnings: [] }) },
		],
		isError: false,
	};
}

const VIDEO = {
	kind: "video",
	mime: "video/mp4",
	name: "clip.mp4",
	reference: "/myprogram/dshplugin/out/clip.mp4",
	bytes: 1234,
};

test("fileUrl encodes the reference into the same-origin endpoint", () => {
	assert.equal(
		fileUrl("/myprogram/dshplugin/out/clip.mp4"),
		"/api/file?path=%2Fmyprogram%2Fdshplugin%2Fout%2Fclip.mp4",
	);
});

test("a video renders a <video> with controls and no autoplay", () => {
	const tree = MediaView(settled(VIDEO));
	const video = find(tree, "video");
	assert.ok(video, "no <video> in the tree");
	assert.equal(video.props.controls, true);
	assert.notEqual(video.props.autoPlay, true);
	assert.match(String(video.props.src), /^\/api\/file\?path=/);
});

test("audio renders <audio> and images render <img>", () => {
	assert.ok(find(MediaView(settled({ ...VIDEO, kind: "audio", mime: "audio/wav" })), "audio"));
	assert.ok(find(MediaView(settled({ ...VIDEO, kind: "image", mime: "image/png" })), "img"));
});

test("a PDF renders its rasterised pages as images plus a way to read the whole file", () => {
	const pdf = { ...VIDEO, kind: "pdf", mime: "application/pdf", name: "r.pdf", pages: 12 };
	const extras = [{ kind: "image", mime: "image/png", name: "page-1.png", reference: "/p/1.png" }];
	const tree = MediaView(settled(pdf, extras));
	assert.ok(find(tree, "img"), "the page preview must be inline");
	assert.ok(findByClass(tree, "manim-media__open"), "the full-document button is missing");
});

test("an unrenderable kind still shows name, size and an open action", () => {
	const tree = MediaView(settled({ ...VIDEO, kind: "other", name: "a.zip", bytes: 2048 }));
	assert.match(textOf(tree), /a\.zip/);
	assert.ok(findByClass(tree, "manim-media__open"));
});

test("a running call shows a loading state, never an empty player", () => {
	const tree = MediaView({ callId: "x", name: "mcp__media__publish_file", argsRaw: "{}" });
	assert.equal(find(tree, "video"), null);
	assert.ok(findByClass(tree, "manim-media__pending"));
});

test("a refusal shows the reason and the hint", () => {
	const block = {
		kind: "tool-result",
		content: [
			{
				type: "text",
				text: JSON.stringify({ ok: false, reason: "too-large", detail: "33 > 32", hint: "压缩" }),
			},
		],
		isError: false,
	};
	const tree = MediaView(block);
	assert.match(textOf(tree), /too-large/);
	assert.match(textOf(tree), /压缩/);
});

test("a malformed result degrades to a plain row instead of throwing", () => {
	const tree = MediaView({ kind: "tool-result", content: [{ type: "text", text: "{{{" }], isError: false });
	assert.ok(tree, "must render something");
	assert.equal(find(tree, "video"), null);
});

// --- tiny tree helpers -------------------------------------------------------

function find(node, type) {
	if (node === null || typeof node !== "object") return null;
	if (Array.isArray(node)) {
		for (const child of node) {
			const hit = find(child, type);
			if (hit) return hit;
		}
		return null;
	}
	if (node.type === type) return node;
	return find(node.props?.children, type);
}

function findByClass(node, className) {
	if (node === null || typeof node !== "object") return null;
	if (Array.isArray(node)) {
		for (const child of node) {
			const hit = findByClass(child, className);
			if (hit) return hit;
		}
		return null;
	}
	const classes = String(node.props?.className ?? "");
	if (classes.split(/\s+/).includes(className)) return node;
	return findByClass(node.props?.children, className);
}

function textOf(node, out = []) {
	if (node === null || node === undefined) return out.join("");
	if (typeof node === "string" || typeof node === "number") {
		out.push(String(node));
		return out.join("");
	}
	if (Array.isArray(node)) {
		for (const child of node) textOf(child, out);
		return out.join("");
	}
	textOf(node.props?.children, out);
	return out.join("");
}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd dsh-media-view && node --test "test/*.test.mjs"`
Expected: FAIL — `apply is added by Task 11` / `MediaView is not a function`

- [ ] **Step 3: 最小实现**

替换 `lib/client.js` 里 `exports.__internals` 与 `exports.apply` 那几行之前的内容，加入渲染器：

```javascript
		const STYLE_ID = "@dsh-media-view/view.css";

		/** Same-origin endpoint. `reference` is host-computed; the client only encodes. */
		function fileUrl(reference) {
			return `/api/file?path=${encodeURIComponent(reference)}`;
		}

		const MEDIA_CSS = `
.manim-media { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--dsw-alias-border-l2); border-radius: 10px; background: var(--dsw-alias-bg-base); color: var(--dsw-alias-label-primary); }
.manim-media__title { font-size: 14px; font-weight: 600; }
.manim-media__meta { font-size: 12px; color: var(--dsw-alias-label-tertiary); }
.manim-media__video, .manim-media__audio { width: 100%; border-radius: 8px; background: var(--dsw-alias-bg-base); }
.manim-media__video { max-height: 60vh; }
.manim-media__image { max-width: 100%; border-radius: 8px; }
.manim-media__pages { display: flex; flex-direction: column; gap: 8px; }
.manim-media__open { align-self: flex-start; background: var(--dsw-alias-interactive-bg-hover); color: inherit; border: 1px solid var(--dsw-alias-border-l2); border-radius: 6px; padding: 4px 10px; font: inherit; cursor: pointer; }
.manim-media__open:hover { background: var(--dsw-alias-interactive-bg-active); }
.manim-media__pending { color: var(--dsw-alias-label-tertiary); font-size: 13px; }
.manim-media__error { color: var(--dsw-alias-label-error, inherit); font-size: 13px; }
.manim-media__hint { color: var(--dsw-alias-label-tertiary); font-size: 12px; }
`;

		function ensureStyle() {
			const doc = globalThis.document;
			if (doc === undefined) return;
			if (doc.querySelector(`style[data-plugin-css="${STYLE_ID}"]`) !== null) return;
			const tag = doc.createElement("style");
			tag.dataset.plugin = "dsh-media-view";
			tag.dataset.pluginCss = STYLE_ID;
			tag.textContent = MEDIA_CSS;
			doc.head.appendChild(tag);
		}

		/**
		 * Open one file in the right column.
		 *
		 * The shipped document preview owns `dsh-resource://file/**` and renders PDFs,
		 * images, Markdown and HTML with pdf.js. `openResource` throws
		 * "no session surface is mounted" until the column's seat binds, so it is
		 * retried; giving up is reported, never silent.
		 */
		function openInRightbar(absolutePath, services = {}, options = {}) {
			const { sidebarRight } = services;
			if (sidebarRight === undefined || typeof sidebarRight.openResource !== "function") {
				return false;
			}
			const address = `dsh-resource://file/absolute/${String(absolutePath)
				.replace(/\\/g, "/")
				.replace(/%3A/gi, ":")
				.split("/")
				.filter((segment) => segment !== "")
				.map((segment) => encodeURIComponent(segment).replace(/%3A/gi, ":"))
				.join("/")}`;
			const attempts = options.attempts ?? 40;
			const delayMs = options.delayMs ?? 50;
			const schedule = options.schedule ?? ((fn) => globalThis.setTimeout(fn, delayMs));
			const warn = options.warn ?? ((message) => console.warn(message));
			let tries = 0;
			const attempt = () => {
				tries += 1;
				try {
					sidebarRight.openResource(address);
					return true;
				} catch (error) {
					if (tries >= attempts) {
						warn(`[dsh-media-view] 无法在右侧栏打开（已重试 ${tries} 次）：${error?.message ?? error}`);
						return false;
					}
					schedule(attempt);
					return false;
				}
			};
			attempt();
			return true;
		}

		function formatBytes(bytes) {
			if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "";
			if (bytes < 1024) return `${bytes} B`;
			if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
			return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
		}

		function shell(className, parts) {
			return h("div", { className: `manim-media ${className}` }, ...parts);
		}

		function openButton(media, services) {
			if (typeof media.path !== "string") return null;
			return h(
				"button",
				{
					className: "manim-media__open",
					type: "button",
					onClick: () => openInRightbar(media.path, services),
				},
				"在右侧栏打开",
			);
		}

		function renderOne(media, services, key) {
			const source = fileUrl(media.reference);
			if (media.kind === "image") {
				return h("img", { key, className: "manim-media__image", src: source, alt: media.name ?? "" });
			}
			if (media.kind === "video") {
				return h("video", { key, className: "manim-media__video", src: source, controls: true, preload: "metadata" });
			}
			if (media.kind === "audio") {
				return h("audio", { key, className: "manim-media__audio", src: source, controls: true, preload: "metadata" });
			}
			return null;
		}

		const MediaView = ({ block, ...services }) => {
			if (block?.kind !== "tool-result") {
				return shell("is-pending", [
					h("div", { className: "manim-media__pending" }, "正在发布文件…"),
				]);
			}
			const envelope = readEnvelope(block);
			if (envelope && envelope.ok === false) {
				return shell("is-refused", [
					h("div", { className: "manim-media__error" }, `发布失败：${envelope.reason ?? "unknown"}`),
					envelope.detail ? h("div", { className: "manim-media__meta" }, envelope.detail) : null,
					envelope.hint ? h("div", { className: "manim-media__hint" }, envelope.hint) : null,
				].filter(Boolean));
			}
			const media = readMedia(envelope);
			if (media === null) {
				return shell("is-generic", [
					h("div", { className: "manim-media__meta" }, "文件已发布（结果无法解析）"),
				]);
			}
			const extras = Array.isArray(envelope.extras) ? envelope.extras : [];
			const parts = [];
			if (media.title) parts.push(h("div", { key: "t", className: "manim-media__title" }, media.title));
			const inline = renderOne(media, services, "main");
			if (inline) parts.push(inline);
			const pages = extras
				.map((extra, index) => renderOne(extra, services, `extra-${index}`))
				.filter(Boolean);
			if (pages.length > 0) {
				parts.push(h("div", { key: "pages", className: "manim-media__pages" }, ...pages));
			}
			parts.push(
				h(
					"div",
					{ key: "meta", className: "manim-media__meta" },
					[media.name, formatBytes(media.bytes), media.pages ? `共 ${media.pages} 页` : null]
						.filter(Boolean)
						.join(" · "),
				),
			);
			const button = openButton(media, services);
			if (button) parts.push(button);
			for (const warning of Array.isArray(envelope.warnings) ? envelope.warnings : []) {
				parts.push(h("div", { key: `w-${warning}`, className: "manim-media__hint" }, warning));
			}
			return shell("is-ready", parts);
		};
```

并把结尾替换为：

```javascript
		exports.__internals = {
			TOOL_KEY,
			readEnvelope,
			readMedia,
			fileUrl,
			formatBytes,
			openInRightbar,
			MediaView,
		};
		exports.inject = ["slots", "sidebarRight"];
		exports.apply = function apply(ctx) {
			ensureStyle();
			const services = { sidebarRight: ctx.sidebarRight };
			ctx.slots.inject("tool.call.toolview", () =>
				ctx.slots.register({ name: "tool.call.toolview", key: TOOL_KEY }, (props) =>
					MediaView({ ...props, ...services }),
				),
			);
		};
		return module.exports;
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd dsh-media-view && node --test "test/*.test.mjs"`
Expected: PASS（4 + 5 + 9 tests, 0 fail）

- [ ] **Step 5: 提交**

```bash
git add dsh-media-view
git commit -m "feat(dsh-media-view): 按 kind 渲染（视频/音频/图片/PDF 预览/其它），加载与拒绝态齐备"
```

---

### Task 12: 安装器改造

**Files:**
- Modify: `tools/dsh_installer.py`
- Test: `tests/test_installer_media.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_installer_media.py
"""Adding a second MCP and a second plugin must not break the byte-for-byte round trip
that is the whole safety argument for letting a script touch ~/.dsh."""

import json
import shutil
from pathlib import Path

import pytest

from dsh_installer import (
    MEDIA_BLOCK_ID,
    MEDIA_PACKAGE,
    Targets,
    apply_install,
    apply_uninstall,
    build_media_insert_block,
    plan_install,
)

GALLERY_PACKAGE = "dsh-manim-gallery"


@pytest.fixture()
def sandbox(tmp_path: Path):
    profile = tmp_path / "profile"
    (profile / "node_modules").mkdir(parents=True)
    (profile / "cordis.patch.yml").write_text("- id: connection\n  config: {}\n", encoding="utf-8")
    (profile / "package.json").write_text(
        json.dumps({"name": "p", "private": True, "dsh": {"profile": {"bundles": []}}, "dependencies": {}}),
        encoding="utf-8",
    )
    source = tmp_path / "src"
    for package in (GALLERY_PACKAGE, MEDIA_PACKAGE):
        (source / package / "lib").mkdir(parents=True)
        (source / package / "lib" / "client.js").write_text("// client\n", encoding="utf-8")
        (source / package / "package.json").write_text("{}", encoding="utf-8")
    (source / "manim-mcp").mkdir()
    (source / "manim-mcp" / "server.py").write_text("# entry\n", encoding="utf-8")
    (source / "media-mcp").mkdir()
    (source / "media-mcp" / "server.py").write_text("# entry\n", encoding="utf-8")
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


def test_the_media_insert_block_mounts_the_mcp_under_its_own_id(sandbox):
    block = build_media_insert_block(sandbox)
    assert f"- id: {MEDIA_BLOCK_ID}" in block
    assert "serverName: media" in block
    assert "media-mcp" in block


def test_the_media_mcp_is_pinned_to_the_same_fs_cwd_as_the_overlay(sandbox):
    """One variable feeds both, so 'same drive' cannot drift into a silent 404."""
    block = build_media_insert_block(sandbox)
    assert sandbox.render_root.parent.as_posix() in block


def test_install_adds_both_plugins_and_both_mcp_rows(sandbox):
    apply_install(sandbox)
    patch = sandbox.patch_file.read_text(encoding="utf-8")
    assert "mcp-manim" in patch and MEDIA_BLOCK_ID in patch
    package = json.loads(sandbox.profile_package.read_text(encoding="utf-8"))
    assert MEDIA_PACKAGE in package["dsh"]["profile"]["bundles"]
    assert package["dependencies"][MEDIA_PACKAGE].startswith("link:")


def test_a_second_plan_reports_no_change(sandbox):
    apply_install(sandbox)
    assert plan_install(sandbox)["changed"] is False


def test_uninstall_restores_the_profile_byte_for_byte(sandbox):
    before_patch = sandbox.patch_file.read_text(encoding="utf-8")
    before_package = sandbox.profile_package.read_text(encoding="utf-8")
    apply_install(sandbox)
    apply_uninstall(sandbox)
    assert sandbox.patch_file.read_text(encoding="utf-8") == before_patch
    assert sandbox.profile_package.read_text(encoding="utf-8") == before_package
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_media.py -q`
Expected: FAIL — `ImportError: cannot import name 'MEDIA_BLOCK_ID'`

- [ ] **Step 3: 最小实现**

在 `tools/dsh_installer.py` 顶部常量区加入：

```python
MEDIA_BLOCK_ID = "mcp-media"
MEDIA_PACKAGE = "dsh-media-view"
```

`Targets.plugin_dir` 现在是**绑死 `GALLERY_PACKAGE` 的 property**（`return self.plugin_root / GALLERY_PACKAGE`），所以第二个插件无处落地。加一个同样形态的属性，而不是把 `plugin_dir` 参数化——参数化会波及 `client_file`、`host_entry`、`skill_dir` 以及所有既有调用点，改动面与收益不成比例：

```python
    @property
    def media_plugin_dir(self) -> Path:
        return self.plugin_root / MEDIA_PACKAGE
```

在 `build_manim_insert_block` 之后加一个同构的构造函数：

```python
def build_media_insert_block(targets: Targets) -> str:
    """The `- insert:` entry that mounts the media MCP.

    `root` here is the SAME expression `build_fs_overlay_block` pins — one source of
    truth for "the artefact and the filesystem provider share a drive", because two
    sources is precisely how the in-answer reference turns into a silent 404.

    The env keys must match `media_mcp.config.load_config` exactly. They are spelled
    out here rather than derived, so a rename shows up as a failing installer test
    instead of a runtime KeyError inside a child process.
    """
    root = targets.render_root.parent
    server = targets.source_root / "media-mcp" / "server.py"
    return "\n".join(
        [
            "# media MCP — 通用文件发布通道（由 install.ps1 维护，可重复执行）",
            "- insert:",
            f"    - id: {MEDIA_BLOCK_ID}",
            "      name: '@deepseek-ai/dsh-mcp-client'",
            "      config:",
            "        serverName: media",
            "        transport: stdio",
            f"        command: {_yaml_scalar(targets.python)}",
            "        args:",
            f"          - {_yaml_scalar(str(server))}",
            "        failOnStartupError: true",
            "        env:",
            f"          MEDIA_MCP_PYTHON: {_yaml_scalar(targets.python)}",
            f"          MEDIA_MCP_FS_CWD: {_yaml_scalar(root.as_posix())}",
            f"          MEDIA_MCP_ROOTS: {_yaml_scalar(root.as_posix())}",
            f"          MEDIA_MCP_PDFTOPPM: {_yaml_scalar(targets.pdftoppm)}",
            f"          MEDIA_MCP_PDFINFO: {_yaml_scalar(targets.pdfinfo)}",
            "",
        ]
    )
```

`targets.pdftoppm` / `targets.pdfinfo` 还不存在。`Targets` 需要两个新字段，并且要和 `manim`/`ffmpeg` 一样由 `_targets_from` 探测（`shutil.which` 回退到 MiKTeX 目录）：

```python
    pdftoppm: str
    pdfinfo: str
```

在 `_add_common_arguments` 对应的探测处加：

```python
def _which_or_miktex(name: str) -> str:
    """`pdftoppm` / `pdfinfo` ship inside MiKTeX, which is not always on PATH."""
    found = shutil.which(name)
    if found:
        return found
    for candidate in (
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "MiKTeX/miktex/bin/x64",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/MiKTeX/miktex/bin/x64",
    ):
        exe = candidate / f"{name}.exe"
        if exe.exists():
            return str(exe)
    return name
```

`_targets_from` 里 `pdftoppm=_which_or_miktex("pdftoppm")`、`pdfinfo=_which_or_miktex("pdfinfo")`。

**测试夹具也要跟着改**：`tests/test_installer_media.py` 与既有 `tests/test_installer_apply.py` 的 `Targets(...)` 构造都要加这两个字段：

```python
        pdftoppm=r"D:\miktex\pdftoppm.exe",
        pdfinfo=r"D:\miktex\pdfinfo.exe",
```

在 `plan_install` 里：把 `("mcp-media", build_media_insert_block(targets))` 加进插入列表；把 `apply_install` 的写入改成同时追加两个块，并把 `plan_package_json` 扩展为接受多个包名（或调用两次）。`apply_install` 的结尾：

```python
    _write(
        targets.patch_file,
        stripped + build_manim_insert_block(targets) + build_media_insert_block(targets) + build_fs_overlay_block(targets),
    )
```

`plan_package_json` 增加 `package: str = GALLERY_PACKAGE` 参数，`apply_install` / `apply_uninstall` 对两个包各调一次。

- [ ] **Step 4: 运行测试确认通过**

Run: `D:\ProgramData\anaconda3\python.exe -m pytest tests/test_installer_media.py tests/test_installer_apply.py tests/test_installer_paths.py tests/test_installer_cli.py -q`
Expected: PASS（全部）

- [ ] **Step 5: 提交**

```bash
git add tools/dsh_installer.py tests/test_installer_media.py
git commit -m "feat(installer): 挂载 media MCP 与 dsh-media-view，卸载逐字节还原"
```

---

### Task 13: 真机安装与端到端验收

**Files:**
- Modify: `README.md`
- Modify: `install.ps1`（如需把新插件纳入 `-RenderRoot` 推导，通常不需要）

- [ ] **Step 1: 全量测试**

Run:
```powershell
D:\ProgramData\anaconda3\python.exe -m pytest tests -q
cd dsh-manim-gallery; node --test "test/*.test.mjs"
cd ..\dsh-media-view; node --test "test/*.test.mjs"
```
Expected: 三套全绿

- [ ] **Step 2: dry-run 看计划**

Run: `.\install.ps1 -DryRun`
Expected: 计划里出现 `mcp-media`、`dsh-media-view`，且没有意外删除

- [ ] **Step 3: 安装**

Run: `.\install.ps1`
Expected: 退出码 0；`verify-selftest` 跑通两个 MCP

- [ ] **Step 4: 重启 web（分离启动，它会杀掉当前 3080 进程）**

Run:
```powershell
Start-Process -FilePath "pwsh" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File","$HOME\.dsh\restart-web.ps1","-DelaySeconds","8") -WindowStyle Hidden
```

- [ ] **Step 5: 确认工具已注册**

用 Inspect 的 `Tool.listTools` 查 `mcp__media__publish_file` 存在。**若不存在**：看 dsh 启动日志里的 `mcp-client(media)`，而不是猜。

- [ ] **Step 6: 用真实 HTTP 验证引用可取**

准备一个真实 mp4 与一个 PDF，各发布一次，然后用既有探针核对引用：

Run:
```powershell
$c = Get-Content "$env:USERPROFILE\.dsh\.credentials.yaml" -Raw
$env:DSH_SECRET = [regex]::Match($c,'client-connection/browser-session:[\s\S]*?secret:\s*(\S+)').Groups[1].Value
node tests/manual/probe_file_api.mjs "<刚发布的 mp4 绝对路径>"
```
Expected: `200 video/mp4`，且字节数与信封 `bytes` 一致

- [ ] **Step 7: 目视验收**

依次确认：视频在对话流里**能播**；音频能播；PDF 显示前 3 页且"在右侧栏打开"能翻完整文档；一个 `.zip` 显示名字/大小/可打开。**这四条只有用户能确认。**

- [ ] **Step 8: 更新 README**

在组件表加一行 `dsh-media-view` 与 `media-mcp`；在排障表加一行「发布后卡片是空的」→ 先查 key 是否逐字正确，再跑 `server.py --doctor`。

- [ ] **Step 9: 提交**

```bash
git add README.md
git commit -m "docs: README 补通用文件发布通道的安装与排障"
```

---

## 自审记录

**规格覆盖检查**（逐个 § 对照任务）：

| 规格 | 落在哪个任务 |
|---|---|
| §2 实测事实 | 作为各任务注释里的依据引用；无独立任务（正确） |
| §3 / §3.1 / §3.2（不覆盖 shipped UI、工具描述即行为层） | Task 11 的 key 断言、Task 9 的描述四问 |
| §4 架构两组件 | Task 1–9（MCP）、Task 10–11（client） |
| §5 数据流 | Task 8（host 侧产出）+ Task 10（client 侧解析） |
| §6.1 六种校验 | Task 5 |
| §6.2 MIME 嗅探 | Task 2 |
| §6.3 kind 分类 | Task 3 |
| §6.4 配置 | Task 1 |
| §6.5 PDF 光栅化 | Task 7 + Task 8 |
| §6.6 工具描述四问 | Task 9 |
| §7.1 注册与 key | Task 11 |
| §7.2 状态机（kind 判别） | Task 10 解析 + Task 11 渲染 |
| §7.3 各 kind 渲染 | Task 11 |
| §7.4 视觉（只用主题 token） | Task 11 的 CSS |
| §8 不允许静默失败 | Task 10（解析不抛）、Task 7（光栅化不致命）、Task 11（拒绝态） |
| §9.1 / §9.2 实测结论 | Task 7 与 Task 10 的注释即其落地 |
| §10 安装卸载 | Task 12 |
| §11 测试策略 | 每个任务的 Step 1 |
| §12 YAGNI | Task 12 只动两个包；未动 manim 卡片与 `present` |
| §13 判据 | Task 13 |

**占位符扫描：** 无 "TBD"/"TODO"/"similar to Task N"。Task 12 Step 3 里两处显式标注了"改这一行前先看 Task 1"，因为那里是跨任务的键名对齐点，写清楚比留一个安静的错更好。

**类型一致性：** `Config` 字段（`roots`/`fs_cwd`/`max_bytes`/`pdf_pages`/`pdf_dpi`/`render_root`/`pdftoppm`/`pdfinfo`/`python`）在 Task 1 定义，Task 5/7/8/9 引用一致；`Rejection(reason, detail, hint)` 在 Task 5 定义、Task 6 消费；信封键 `ok/media/extras/warnings/reason/detail/hint` 在 Task 6 定义，Task 10/11 的 client 侧读的是同一组；`TOOL_KEY` 在 Task 10 定义、Task 11 断言。

**已知的跨任务风险（写进计划而不是留给运气）：** Task 12 的 env 键名必须与 Task 1 的 `load_config` 对齐；Step 3 里已用引用块显式标出。
