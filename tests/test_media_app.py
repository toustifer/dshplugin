from media_mcp.app import TOOL_DESCRIPTION, build_server


def test_the_description_answers_all_four_behaviour_questions():
    assert "什么时候" in TOOL_DESCRIPTION or "该发" in TOOL_DESCRIPTION
    assert "不要" in TOOL_DESCRIPTION or "不该" in TOOL_DESCRIPTION
    assert "3" in TOOL_DESCRIPTION  # the per-turn budget
    assert "MiB" in TOOL_DESCRIPTION or "上限" in TOOL_DESCRIPTION


def test_the_description_says_a_refusal_carries_a_reason():
    assert "reason" in TOOL_DESCRIPTION


def test_the_server_exposes_exactly_one_tool_named_publish_file():
    server = build_server()
    names = {tool.name for tool in server._tool_manager.list_tools()}  # noqa: SLF001
    assert names == {"publish_file"}
