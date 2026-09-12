"""Placeholder replaced in a later task."""

from . import SceneSpecError

NAME = "compare"
SCENE_CLASS = "CompareScene"
SUMMARY = "左右对照（占位，后续任务补全）"
PARAMS: dict = {}


def build(**kwargs) -> str:
    raise SceneSpecError("this template is not implemented yet")
