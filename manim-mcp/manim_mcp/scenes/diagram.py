"""Placeholder replaced in a later task."""

from . import SceneSpecError

NAME = "diagram"
SCENE_CLASS = "DiagramScene"
SUMMARY = "流程框图（占位，后续任务补全）"
PARAMS: dict = {}


def build(**kwargs) -> str:
    raise SceneSpecError("this template is not implemented yet")
