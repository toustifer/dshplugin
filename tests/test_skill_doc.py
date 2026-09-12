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

TOOL_RAW_NAMES = (
    "equation", "graph", "diagram", "compare", "render", "check", "style_guide", "runs",
)


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


def test_the_preview_requirement_covers_the_null_case():
    """`previewMarkdown` is null when the artifact is outside the render root.

    The failure mode this guards against: the model guesses a path to keep the
    animation inline, and the answer ships a broken image next to a working tool
    card.
    """
    assert "null" in TEXT
    assert "伪造" in TEXT or "不要编" in TEXT


def test_the_one_sentence_requirement_is_present():
    """An animation without a sentence naming the relation it shows is decoration."""
    assert "一句话" in TEXT


def test_the_budget_guardrail_is_present():
    assert "最多 1 个" in TEXT or "最多一个" in TEXT


def test_the_draft_quality_default_is_stated():
    assert "draft" in TEXT


def test_the_failure_isolation_rule_is_present():
    assert "不阻塞" in TEXT or "照常" in TEXT


def test_the_skill_tells_the_model_when_not_to_animate():
    assert "闲聊" in TEXT or "不画" in TEXT


def test_the_default_duration_is_stated():
    assert "8" in TEXT and "20" in TEXT


def test_the_skill_points_at_the_runs_tool_for_iterating():
    """Otherwise the model rewrites a scene from memory instead of reading it back."""
    assert "mcp__manim__runs" in TEXT
