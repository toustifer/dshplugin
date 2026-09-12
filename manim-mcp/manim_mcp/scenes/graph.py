"""Placeholder replaced in a later task."""

from . import SceneSpecError

NAME = "graph"
SCENE_CLASS = "GraphScene"
SUMMARY = "函数图像（占位，后续任务补全）"
PARAMS: dict = {}


def build(**kwargs) -> str:
    raise SceneSpecError("this template is not implemented yet")
