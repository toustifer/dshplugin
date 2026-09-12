"""Static pre-flight: reject what Manim would reject, in a tenth of a second."""

from __future__ import annotations

import ast

from . import envelope

IMPORT_HINT = "from manim import *"


def _scene_classes(tree: ast.Module) -> list[ast.ClassDef]:
    found: list[ast.ClassDef] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            if name == "Scene":
                found.append(node)
                break
    return found


def _imports_manim(tree: ast.Module) -> bool:
    """Whether the module pulls Manim in at all.

    `from manim import *` is the documented form, but `import manim` plus
    `manim.Scene` renders exactly as well, so testing for one literal string
    would reject working code.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name == "manim" or alias.name.startswith("manim.")
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "manim" or module.startswith("manim."):
                return True
    return False


def check_code(code: str) -> dict:
    """Report whether `code` is plausibly renderable, without running Manim."""
    if not isinstance(code, str) or not code.strip():
        return envelope.plain_payload(
            ok=False, issues=["code 为空：需要一段完整的 Manim 场景代码"], sceneClasses=[]
        )

    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return envelope.plain_payload(
            ok=False,
            issues=[f"语法错误：第 {error.lineno} 行 {error.msg}"],
            sceneClasses=[],
        )

    issues: list[str] = []
    classes = _scene_classes(tree)

    if not _imports_manim(tree):
        issues.append(f"缺少 `{IMPORT_HINT}`，Manim 的图形类会全部未定义")

    if not classes:
        issues.append("没有找到继承自 `Scene` 的类，Manim 无从渲染")
    else:
        for node in classes:
            if not any(
                isinstance(item, ast.FunctionDef) and item.name == "construct"
                for item in node.body
            ):
                issues.append(f"场景类 `{node.name}` 缺少 `construct` 方法")

    return envelope.plain_payload(
        ok=not issues,
        issues=issues,
        sceneClasses=[node.name for node in classes],
        suggestedScene=classes[0].name if classes else None,
        lineCount=len(code.splitlines()),
    )
