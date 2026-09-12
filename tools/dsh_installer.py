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

import argparse
import dataclasses
import json
import re
import shutil
import sys
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

    _, package_changed = plan_package_json(
        _read(targets.profile_package), plugin_dir=targets.plugin_dir
    )

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
    return {
        "action": "install",
        "changed": changed,
        "steps": [step.as_dict() for step in steps],
    }


def plan_uninstall(targets: Targets) -> dict:
    _, present = remove_insert_block(_read(targets.patch_file), MANIM_BLOCK_ID)
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
    return {
        "action": "uninstall",
        "changed": changed,
        "steps": [step.as_dict() for step in steps],
    }


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

    # Guarded because the file-surgery tests run without a copy, and
    # `patch_client_render_root` refuses to guess when its line is absent.
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
    if link.is_symlink() or link.is_file():
        link.unlink()
    elif link.is_dir():
        shutil.rmtree(link)

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


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile-root", required=True, type=Path)
    parser.add_argument("--plugin-root", type=Path, default=Path.home() / ".dsh" / "plugins")
    parser.add_argument("--skill-root", type=Path, default=Path.home() / ".dsh" / "skills")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--render-root", required=True, type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--manim", default=None)
    parser.add_argument("--ffmpeg", default=None)
    parser.add_argument("--dry-run", action="store_true")


def _targets_from(args: argparse.Namespace) -> Targets:
    source = args.source_root.resolve()
    if not (source / GALLERY_PACKAGE).is_dir():
        raise InstallerError(
            f"--source-root {source} does not contain {GALLERY_PACKAGE}/; "
            "point it at the directory that holds this repository"
        )
    if not (source / "manim-mcp" / "server.py").is_file():
        raise InstallerError(f"--source-root {source} does not contain manim-mcp/server.py")
    # Checked here rather than left to the JSON parser: a wrong --profile-root is
    # the likeliest mistake, and "not valid JSON" for a missing file sends the
    # reader looking in the wrong place.
    if not (args.profile_root / "package.json").is_file():
        raise InstallerError(
            f"--profile-root {args.profile_root} has no package.json; point it at a "
            "DSH profile directory (normally ~/.dsh/profiles/web)"
        )
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
        prog="dsh_installer",
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
