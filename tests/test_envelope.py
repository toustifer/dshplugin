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


def test_preview_markdown_drops_the_drive_and_keeps_every_directory():
    """The Host resolves a `/`-rooted reference against the filesystem cwd's *drive*.

    Measured with `node:path.resolve`:
      * `resolve('D:\\\\proj', '/myprogram/dshplugin/renders/x.gif')`
        -> `D:\\myprogram\\dshplugin\\renders\\x.gif`  (reaches the file)
      * `resolve('D:\\\\proj', '/renders/x.gif')` -> `D:\\renders\\x.gif`  (misses)
      * `resolve('D:\\\\proj', '/D:/myprogram/x.gif')` -> `D:\\D:\\myprogram\\x.gif`  (misses)

    So the reference is the full absolute path minus the drive letter, and the
    pinned cwd only has to supply the right drive. An earlier design emitted
    `/renders/<run>/out/S.gif`; it 404'd, which is what this pins down.
    """
    assert envelope.preview_markdown(
        r"D:\myprogram\dshplugin\renders\r1\out\S.gif",
        r"D:\myprogram\dshplugin\renders",
    ) == "![anim](/myprogram/dshplugin/renders/r1/out/S.gif)"


def test_rooted_reference_handles_both_host_shapes():
    assert envelope.rooted_reference("D:/a/b/c.gif") == "/a/b/c.gif"
    assert envelope.rooted_reference("C:/a/b/c.gif") == "/a/b/c.gif"
    assert envelope.rooted_reference("/a/b/c.gif") == "/a/b/c.gif"


def test_rooted_reference_refuses_paths_with_no_same_origin_form():
    assert envelope.rooted_reference("//server/share/a.gif") is None  # UNC
    assert envelope.rooted_reference("relative/a.gif") is None
    assert envelope.rooted_reference("") is None


def test_preview_markdown_refuses_an_unknown_render_root():
    """A reference that cannot resolve must not be emitted at all: a broken image in
    the answer is worse than no image, because the answer still shows the real one
    from the tool result."""
    assert envelope.preview_markdown(r"D:\r\S.gif") is None


def test_preview_markdown_refuses_an_artifact_outside_the_render_root():
    assert envelope.preview_markdown(r"D:\elsewhere\S.gif", r"D:\renders") is None


def test_preview_markdown_rejects_a_path_with_markdown_breaking_characters():
    assert envelope.preview_markdown(r"D:\renders\my (dir)\S.gif", r"D:\renders") is None
    assert envelope.preview_markdown(r"D:\renders\我的目录\S.gif", r"D:\renders") is None
