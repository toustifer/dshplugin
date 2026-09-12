"""The installer rewrites a user's profile, so every transformation is a pure,
separately assertable function rather than a side effect buried in a script.
"""

import json
from pathlib import Path

import pytest

from dsh_installer import (
    GALLERY_PACKAGE,
    MANIM_BLOCK_ID,
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
    assert subject.module_link == tmp_path / "profile" / "node_modules" / GALLERY_PACKAGE


def test_targets_reject_a_relative_render_root():
    with pytest.raises(InstallerError) as caught:
        Targets(
            profile_root=Path("p"), plugin_root=Path("l"), skill_root=Path("s"),
            source_root=Path("x"), render_root=Path("renders"),
            python="p", manim=None, ffmpeg=None,
        )
    assert "render_root" in str(caught.value)


def test_targets_replace_returns_a_changed_copy(tmp_path: Path):
    subject = targets(tmp_path)
    without_manim = subject.replace(manim=None)
    assert without_manim.manim is None
    assert subject.manim is not None


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
    block = build_manim_insert_block(targets(tmp_path).replace(manim=None))
    assert "MANIM_MCP_MANIM" not in block
    assert "MANIM_MCP_PYTHON" in block


def test_manim_block_omits_ffmpeg_when_it_was_not_found(tmp_path: Path):
    block = build_manim_insert_block(targets(tmp_path).replace(ffmpeg=None))
    assert "MANIM_MCP_FFMPEG" not in block
    assert "MANIM_MCP_PYTHON" in block


def test_manim_block_quotes_paths_so_backslashes_stay_literal(tmp_path: Path):
    block = build_manim_insert_block(targets(tmp_path))
    assert "command: 'D:\\py\\python.exe'" in block


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
    assert stripped.count("- insert:") == 1


def test_remove_insert_block_handles_an_entry_at_end_of_file():
    text = "- id: a\n- insert:\n    - id: mcp-manim\n      name: x\n"
    stripped, removed = remove_insert_block(text, MANIM_BLOCK_ID)
    assert removed is True
    assert stripped.strip() == "- id: a"


def test_remove_insert_block_does_not_eat_an_unrelated_comment():
    text = (
        "# unrelated\n"
        "- id: a\n"
        "\n"
        "# manim MCP — mine\n"
        "- insert:\n"
        "    - id: mcp-manim\n"
        "      name: x\n"
    )
    stripped, _ = remove_insert_block(text, MANIM_BLOCK_ID)
    assert "# unrelated" in stripped
    assert "# manim MCP — mine" not in stripped


def test_remove_insert_block_keeps_nested_list_items_inside_the_entry():
    """A nested `- item` must not be mistaken for the next top-level entry."""
    text = (
        "- insert:\n"
        "    - id: mcp-manim\n"
        "      config:\n"
        "        args:\n"
        "          - 'D:\\a\\server.py'\n"
        "          - '--flag'\n"
        "- id: after\n"
    )
    stripped, removed = remove_insert_block(text, MANIM_BLOCK_ID)
    assert removed is True
    assert stripped.strip() == "- id: after"


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


def test_plan_package_json_refuses_a_non_object_document():
    with pytest.raises(InstallerError):
        plan_package_json("[1, 2]", plugin_dir=Path("C:/plug"))


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


def test_patch_client_render_root_preserves_indentation():
    patched, _ = patch_client_render_root(
        '\tconst RENDER_ROOT = "D:/old";\n', Path("D:/new")
    )
    assert patched.startswith('\tconst RENDER_ROOT = "D:/new";')


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
