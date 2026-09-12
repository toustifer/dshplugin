"""Declarative scene templates.

A template owns one *kind* of explanation. It validates the model's arguments and
compiles them into a complete, flat Manim source file — flat on purpose, because
the model may have to read and repair that file on the next turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping


class SceneSpecError(ValueError):
    """The supplied arguments cannot be turned into a scene.

    Raised before any rendering happens, so a bad argument costs milliseconds
    instead of a ten-second Manim run.
    """


@dataclass(frozen=True)
class SceneTemplate:
    """One declarative tool's code generator."""

    name: str
    scene_class: str
    summary: str
    params: Mapping[str, str]
    build: Callable[..., str]
    _cache: dict = field(default_factory=dict, repr=False, compare=False)


def _load() -> dict[str, SceneTemplate]:
    from . import compare, diagram, equation, graph

    templates: list[SceneTemplate] = []
    for module in (equation, graph, diagram, compare):
        templates.append(
            SceneTemplate(
                name=module.NAME,
                scene_class=module.SCENE_CLASS,
                summary=module.SUMMARY,
                params=dict(module.PARAMS),
                build=module.build,
            )
        )
    return {template.name: template for template in templates}


_CACHE: dict[str, SceneTemplate] | None = None


def registry() -> dict[str, SceneTemplate]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load()
    return _CACHE


def build(template_name: str, **params) -> tuple[str, str]:
    """Compile a template into `(scene_class, source)`."""
    template = registry().get(template_name)
    if template is None:
        known = ", ".join(sorted(registry()))
        raise SceneSpecError(f"unknown template {template_name!r}; known templates: {known}")
    code = template.build(**params)
    return template.scene_class, code


def catalogue() -> list[dict]:
    """The machine-readable template list `style_guide` hands to the model."""
    return [
        {
            "name": template.name,
            "sceneClass": template.scene_class,
            "summary": template.summary,
            "params": dict(template.params),
        }
        for template in sorted(registry().values(), key=lambda item: item.name)
    ]
