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
        "pin-fs-cwd",
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
    assert flags["pin-fs-cwd"]["changed"] is False
    # The MCP row is always replaced (remove + append is how idempotence works),
    # so it is the one step that legitimately still reports a change.
    assert flags["yaml-insert"]["replaced"] is True
    assert again["changed"] is False


def test_plan_install_notices_a_stale_comment_on_an_otherwise_correct_overlay(
    sandbox: Targets,
):
    """`changed` must mean "the file already matches", not "the cwd value matches".

    The bug this pins down: the check used to ask only whether the `cwd:` line was
    present, so after the block's explanatory comment was rewritten the plan still
    reported `changed: false` for a run that did rewrite the file. A plan that
    under-reports is how a stale comment survives a reinstall unnoticed.
    """
    apply_install(sandbox)
    text = sandbox.patch_file.read_text(encoding="utf-8")
    sandbox.patch_file.write_text(
        text.replace("盘符", "旧口径").replace("丢掉它的目录", "旧的解释"), encoding="utf-8"
    )

    changes = {step["kind"]: step for step in plan_install(sandbox)["steps"]}
    assert changes["pin-fs-cwd"]["changed"] is True
    assert plan_install(sandbox)["changed"] is True


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
    assert [entry.get("id") for entry in parsed if "id" in entry] == [
        "connection",
        "fs-sandbox",
    ]
    inserts = [entry["insert"][0]["id"] for entry in parsed if "insert" in entry]
    assert inserts == ["mcp-agentflow", "mcp-manim"]

    # The overlay is what makes the Markdown channel's rooted path resolve.
    overlay = [entry for entry in parsed if entry.get("id") == "fs-sandbox"][0]
    assert overlay["config"]["cwd"] == sandbox.render_root.parent.as_posix()


def test_apply_install_writes_a_backup_next_to_the_patch_file(sandbox: Targets):
    apply_install(sandbox)
    backups = list(sandbox.profile_root.glob("cordis.patch.yml.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == PROFILE_PATCH


def test_apply_install_adds_the_bundle_and_the_link(sandbox: Targets):
    apply_install(sandbox)
    data = json.loads(sandbox.profile_package.read_text(encoding="utf-8"))
    assert data["dsh"]["profile"]["bundles"] == [
        "@deepseek-ai/dsh-base",
        "dsh-harvest",
        GALLERY_PACKAGE,
    ]
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


def test_apply_install_creates_the_node_modules_link(sandbox: Targets):
    apply_install(sandbox)
    link = sandbox.module_link
    assert link.is_symlink()
    assert link.resolve() == sandbox.plugin_dir.resolve()


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
    assert not sandbox.module_link.exists() and not sandbox.module_link.is_symlink()


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


def test_uninstall_can_purge_renders_on_request(sandbox: Targets):
    apply_install(sandbox)
    rendered = sandbox.render_root / "20260912-153012-a1b2" / "out" / "S.gif"
    rendered.parent.mkdir(parents=True)
    rendered.write_bytes(b"gif")
    apply_uninstall(sandbox, purge_renders=True)
    assert not rendered.exists()


def test_plan_uninstall_reports_what_it_would_remove(sandbox: Targets):
    apply_install(sandbox)
    plan = plan_uninstall(sandbox)
    kinds = [step["kind"] for step in plan["steps"]]
    assert kinds == [
        "backup",
        "yaml-remove",
        "unpin-fs-cwd",
        "remove-package-json-entry",
        "remove-plugin-dir",
        "remove-skill-dir",
        "unlink-package",
    ]
    flags = {step["kind"]: step for step in plan["steps"]}
    assert flags["yaml-remove"]["present"] is True
    assert flags["unpin-fs-cwd"]["present"] is True
    assert flags["remove-plugin-dir"]["changed"] is True
    assert plan["changed"] is True


def test_plan_uninstall_on_a_clean_profile_reports_nothing_to_do(sandbox: Targets):
    plan = plan_uninstall(sandbox)
    assert plan["changed"] is False


def test_reinstall_after_uninstall_restores_the_same_text(sandbox: Targets):
    """The second install must land on the same bytes as the first."""
    apply_install(sandbox)
    first = sandbox.patch_file.read_text(encoding="utf-8")
    apply_uninstall(sandbox)
    apply_install(sandbox)
    assert sandbox.patch_file.read_text(encoding="utf-8") == first
