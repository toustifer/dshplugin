"""Installer core for the Manim visual-explainer plugin set.

This is NOT an MCP tool module. It rewrites the user's DSH profile, so every
transformation is a pure function of its inputs: the planning functions return the
text that *would* be written and a flag saying whether anything changed, and only
`apply_install` / `apply_uninstall` touch the disk. That split is what lets the
tests assert on the risky part — YAML surgery that must preserve comments, and a
`package.json` edit that must not disturb the entries it does not own.

Named `dsh_installer` rather than `installer` on purpose: `installer` is a real
distribution on PyPI, and shadowing it through `sys.path` ordering would make the
import depend on who ran first.
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

RENDER_ROOT_LINE_RE = re.compile(
    r'^(?P<indent>\s*)const RENDER_ROOT = "(?P<value>[^"]*)";$', re.MULTILINE
)


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
    env_lines = [f"          MANIM_MCP_PYTHON: {_yaml_scalar(targets.python)}"]
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

        # Walk back to the top-level `- ` header that owns this row.
        start = index
        while start > 0 and not lines[start].startswith("- "):
            start -= 1
        if not lines[start].startswith("- "):
            raise InstallerError(f"found id: {block_id} but no owning top-level entry")

        # The entry ends at the next top-level `- ` line, or EOF. Nested list items
        # are indented, so they cannot terminate it.
        end = len(lines)
        for cursor in range(start + 1, len(lines)):
            if lines[cursor].startswith("- "):
                end = cursor
                break

        # Blank lines and comments directly above the NEXT entry belong to that
        # entry — cutting at `end` verbatim would leave the next row without the
        # comment that explains it. With no next entry the same walk trims this
        # entry's own trailing padding.
        while end > start + 1 and (
            lines[end - 1].strip() == "" or lines[end - 1].lstrip().startswith("#")
        ):
            end -= 1

        # The comment block and blank lines directly above THIS entry explain it, so
        # they leave with it. A comment separated by a blank line is not ours.
        head = start
        while head > 0 and lines[head - 1].lstrip().startswith("#"):
            head -= 1
        while head > 0 and lines[head - 1].strip() == "":
            head -= 1

        return "".join(lines[:head] + lines[end:]), True

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
            'lib/client.js has no `const RENDER_ROOT = "...";` line; '
            "the panel and the MCP would disagree about where the runs live"
        )
    if match.group("value") == wanted:
        return text, False
    replaced = RENDER_ROOT_LINE_RE.sub(
        lambda m: f'{m.group("indent")}const RENDER_ROOT = "{wanted}";', text, count=1
    )
    return replaced, True
