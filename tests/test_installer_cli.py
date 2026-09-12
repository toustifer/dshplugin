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


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALLER), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def plan_of(result: subprocess.CompletedProcess) -> dict:
    text = result.stdout
    return json.loads(text[text.index("{"):])


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

    plan = plan_of(result)
    assert plan["action"] == "install"
    assert plan["changed"] is True
    assert (profile / "cordis.patch.yml").read_text(encoding="utf-8") == before
    assert not (tmp_path / "plugins").exists()
    assert not (tmp_path / "skills").exists()


def test_apply_then_dry_run_reports_nothing_left_to_do(sandbox):
    applied = run("install", *common(sandbox))
    assert applied.returncode == 0, applied.stderr

    result = run("install", *common(sandbox), "--dry-run")
    assert result.returncode == 0, result.stderr
    plan = plan_of(result)
    assert plan["changed"] is False
    flags = {step["kind"]: step for step in plan["steps"]}
    assert flags["copy-plugin"]["changed"] is False
    assert flags["patch-package-json"]["changed"] is False
    assert flags["copy-skill"]["changed"] is False


def test_uninstall_dry_run_changes_nothing(sandbox):
    applied = run("install", *common(sandbox))
    assert applied.returncode == 0, applied.stderr
    _, profile, _ = sandbox
    installed = (profile / "cordis.patch.yml").read_text(encoding="utf-8")
    # Without this the test would also pass against a script that does nothing.
    assert "mcp-manim" in installed

    result = run("uninstall", *common(sandbox), "--dry-run")
    assert result.returncode == 0, result.stderr
    assert (profile / "cordis.patch.yml").read_text(encoding="utf-8") == installed
    assert plan_of(result)["changed"] is True


def test_uninstall_then_reinstall_round_trips_through_the_cli(sandbox):
    _, profile, _ = sandbox
    before = (profile / "cordis.patch.yml").read_text(encoding="utf-8")

    applied = run("install", *common(sandbox))
    assert applied.returncode == 0, applied.stderr
    assert "mcp-manim" in (profile / "cordis.patch.yml").read_text(encoding="utf-8")

    removed = run("uninstall", *common(sandbox))
    assert removed.returncode == 0, removed.stderr
    assert (profile / "cordis.patch.yml").read_text(encoding="utf-8") == before
    assert not (sandbox[0] / "plugins" / "dsh-manim-gallery").exists()


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


def test_a_wrong_profile_root_names_the_actual_problem(sandbox):
    """A missing package.json must not be reported as malformed JSON."""
    args = common(sandbox)
    args[args.index("--profile-root") + 1] = str(sandbox[0] / "not-a-profile")
    result = run("install", *args, "--dry-run")
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "has no package.json" in combined
    assert "profiles/web" in combined
    assert "not valid JSON" not in combined


def test_the_powershell_entry_points_are_thin_wrappers():
    """The pwsh files must not reimplement the file surgery they delegate to Python.

    Asserted on *code*, not on words: the scripts' own help text explains that they
    do not touch YAML, so a naive `"yaml" in text` check would fail on the comment
    that describes the design.
    """
    install = (REPO / "install.ps1").read_text(encoding="utf-8-sig")
    assert "dsh_installer.py" in install
    assert '"install"' in install
    for forbidden in ("ConvertFrom-Json", "ConvertFrom-Yaml", "Set-Content", "Out-File", "Add-Content"):
        assert forbidden not in install, f"install.ps1 reimplements {forbidden}"

    uninstall = (REPO / "uninstall.ps1").read_text(encoding="utf-8-sig")
    assert "dsh_installer.py" in uninstall
    assert '"uninstall"' in uninstall
    for forbidden in ("ConvertFrom-Json", "ConvertFrom-Yaml", "Set-Content", "Out-File", "Add-Content"):
        assert forbidden not in uninstall, f"uninstall.ps1 reimplements {forbidden}"
