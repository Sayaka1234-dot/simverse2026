"""Lamp validator. Implements docs/EVAL_CONTRACT.md §4.

Public entry points:
    validate(parsed_answer, gold_answer, task, project_root) -> Verdict
    validate_task_answer(task, raw_text, ...) -> ParsedAnswer        [backward compat]

`parsed_answer` and `gold_answer` use the SAME schema (lamp's `actions` array).
Validation runs the geometry engine on `parsed_answer`; gold_answer is kept on
the side as one known-valid reference for solver-coverage statistics, but the
verdict is determined by the engine, not by string equality.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine_interface import evaluate_solution
from eval_common.schemas import LampTask, ParsedAnswer
from parsers import parse_lamp_answer


@dataclass
class Verdict:
    status: str                    # "passed" | "failed" | "invalid_output"
    score: float                   # 0.0 .. 1.0
    errors: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def _angles_from_actions(actions: list[dict[str, Any]], segment_count: int) -> list[int]:
    """Return angles indexed 0..segment_count-1 (joint i goes to index i-1)."""
    angles = [0] * segment_count
    for action in actions:
        joint = int(action["joint"])
        angles[joint - 1] = int(action["angle"])
    return angles


def validate(
    *,
    parsed_answer: dict[str, Any],
    gold_answer: dict[str, Any],
    task: dict[str, Any] | LampTask,
    project_root: Path | None = None,
) -> Verdict:
    """Run the geometry engine on the model's `actions` and report a verdict.

    `parsed_answer` and `gold_answer` are both `{"actions": [...]}` per
    docs/PROMPT_SKELETON.md §3.5.
    """
    if isinstance(task, dict):
        lamp_task = LampTask.from_dict(task)
    else:
        lamp_task = task

    actions = parsed_answer.get("actions")
    if not isinstance(actions, list) or not actions:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["actions_missing_or_empty"],
            detail={},
        )

    segment_count = lamp_task.segment_count
    if len(actions) != segment_count:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["actions_length_mismatch"],
            detail={
                "expected_segment_count": segment_count,
                "received": len(actions),
            },
        )

    try:
        angles = _angles_from_actions(actions, segment_count)
    except (KeyError, ValueError, TypeError):
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["actions_missing_joint_or_angle"],
            detail={},
        )

    engine_result = evaluate_solution(
        origin=lamp_task.arm_base,
        segments=lamp_task.segments,
        angles=angles,
        target=lamp_task.target,
        light_radius=lamp_task.light_radius,
        obstacles=lamp_task.obstacles,
    )
    is_solved = bool(engine_result.get("is_valid_solution", False))

    if is_solved:
        return Verdict(
            status="passed",
            score=1.0,
            errors=[],
            detail={"engine_result": engine_result, "gold_answer": gold_answer},
        )

    errors: list[str] = []
    if engine_result.get("collision_with_obstacle"):
        errors.append("rod_intersects_obstacle")
    distance = engine_result.get("distance")
    light_radius = lamp_task.light_radius
    if isinstance(distance, (int, float)) and isinstance(light_radius, (int, float)):
        if float(distance) > float(light_radius) and not engine_result.get("collision_with_obstacle"):
            errors.append("bulb_misses_target")
    if not errors:
        errors.append("solution_failed")

    return Verdict(
        status="failed",
        score=0.0,
        errors=errors,
        detail={"engine_result": engine_result, "gold_answer": gold_answer},
    )


# ---------- backward-compat shim for the legacy provider variants ----------

def validate_task_answer(
    task: LampTask,
    raw_text: str,
    *,
    allow_missing_joints: bool = False,
    missing_joint_default_angle: int = 0,
) -> ParsedAnswer:
    """Legacy API: parse the model reply into a ParsedAnswer (structural only).

    The engine validation now lives in `validate()`. New runners should call
    `parsers.parse_lamp_answer` for parsing and this module's `validate()`
    for engine validation. Kept here so the provider variants don't break
    during the transition; will be removed once the variants are rewritten.
    """
    return parse_lamp_answer(
        raw_text,
        task,
        allow_missing_joints=allow_missing_joints,
        missing_joint_default_angle=missing_joint_default_angle,
    )
