"""Cube2 validator. Implements docs/EVAL_CONTRACT.md §4.

Public entry point:
    validate(parsed_answer, gold_answer, task, project_root) -> Verdict

Cube2 is open-ended: many sequences may produce the target top face. The
validator simulates the model's `directions` on the initial cube state via
`engine_interface.evaluate_with_project_engine` and reports whether the final
top face matches the target. `gold_answer` is one known-valid reference
sequence kept for solver-coverage statistics, not for equality checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine_interface import evaluate_with_project_engine
from eval_common import (
    DEFAULT_MAX_DIRECTION_STEPS,
    GoalRollTask,
    ModelAnswer,
    VALID_DIRECTIONS,
)


_VALID_DIRECTIONS_SET = set(VALID_DIRECTIONS)


@dataclass
class Verdict:
    status: str                    # "passed" | "failed" | "invalid_output"
    score: float                   # 0.0 .. 1.0
    errors: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def validate(
    *,
    parsed_answer: dict[str, Any],
    gold_answer: dict[str, Any],
    task: dict[str, Any] | GoalRollTask,
    project_root: Path | None = None,
) -> Verdict:
    if isinstance(task, dict):
        goal_task = GoalRollTask.from_dict(task)
    else:
        goal_task = task

    directions = parsed_answer.get("directions") if isinstance(parsed_answer, dict) else None
    if not isinstance(directions, list) or not directions:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["directions_missing_or_empty"],
            detail={},
        )
    if len(directions) > DEFAULT_MAX_DIRECTION_STEPS:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["directions_length_exceeds_max"],
            detail={"max_steps": DEFAULT_MAX_DIRECTION_STEPS, "received": len(directions)},
        )

    normalized: list[str] = []
    for token in directions:
        upper = str(token).strip().upper()
        if upper not in _VALID_DIRECTIONS_SET:
            return Verdict(
                status="invalid_output",
                score=0.0,
                errors=[f"bad_direction_token_{token!r}"],
                detail={},
            )
        normalized.append(upper)

    answer = ModelAnswer(sample_id=goal_task.sample_id, directions=normalized, raw_text="")
    engine_result = evaluate_with_project_engine(goal_task, answer)

    matched = bool(engine_result.get("is_fully_correct", False))
    if matched:
        return Verdict(
            status="passed",
            score=1.0,
            errors=[],
            detail={"engine_result": engine_result, "gold_answer": gold_answer},
        )

    errors: list[str] = []
    if engine_result.get("is_pattern_correct") and not engine_result.get("is_pattern_and_rotation_correct"):
        errors.append("rotation_mismatch_top_face")
    elif not engine_result.get("is_pattern_correct"):
        errors.append("pattern_mismatch_top_face")
    else:
        errors.append("solution_failed")

    return Verdict(
        status="failed",
        score=0.0,
        errors=errors,
        detail={"engine_result": engine_result, "gold_answer": gold_answer},
    )
