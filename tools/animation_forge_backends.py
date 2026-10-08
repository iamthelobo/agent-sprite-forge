"""Explicit schema dispatch for original authoring and the local reference walk.

The default remains the portable original mannequin. Selecting the reference
backend is an explicit schema choice; it never turns source motion into original
art or silently substitutes a different rig when local evidence is unavailable.
"""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

if __package__:
    from . import animation_forge_core as authored
else:
    import animation_forge_core as authored

WALK_SCHEMA = "other-animation-forge.walk.v1"


def backend_for(project: Any) -> ModuleType:
    if not isinstance(project, dict):
        raise ValueError("Animation Forge project must be an object")
    schema = project.get("schema")
    if schema == authored.SCHEMA:
        return authored
    if schema == WALK_SCHEMA:
        return importlib.import_module(".animation_forge_walk", __package__) if __package__ else importlib.import_module("animation_forge_walk")
    raise ValueError(f"Unsupported Animation Forge schema: {schema!r}")


def default_project() -> dict:
    return authored.default_project()


def validate_project(project: Any) -> None:
    backend_for(project).validate_project(project)


def evaluate_pose(project: dict, pose_id: str, baseline: bool = False) -> dict:
    return backend_for(project).evaluate_pose(project, pose_id, baseline=baseline)


def render_pose(project: dict, pose_id: str, baseline: bool = False, facing: str = "right"):
    return backend_for(project).render_pose(project, pose_id, baseline=baseline, facing=facing)


def total_ticks(project: dict) -> int:
    return backend_for(project).total_ticks(project)


def pose_at_tick(project: dict, tick: int) -> str:
    return backend_for(project).pose_at_tick(project, tick)
