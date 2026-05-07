"""VOI validator. Implements docs/EVAL_CONTRACT.md §4.

Public entry point:
    validate(parsed_answer, gold_answer, task, project_root) -> Verdict

The pixel engine (`engine_interface.evaluate_with_project_engine`) is the source
of truth for "did the placements reproduce the target pattern". Its existing
input is a text DSL (one `Shape Angle Vertex [x,y]` line per placement); we
convert the JSON `placements` list to that DSL so the engine stays unchanged.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine_interface import evaluate_with_project_engine
from parsers import placements_to_dsl


@dataclass
class Verdict:
    status: str                    # "passed" | "failed" | "invalid_output"
    score: float                   # 0.0 .. 1.0  (uses pattern IoU when not a perfect match)
    errors: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def _placements_from_answer(answer: dict[str, Any]) -> list[dict[str, Any]] | None:
    if not isinstance(answer, dict):
        return None
    placements = answer.get("placements")
    if not isinstance(placements, list) or not placements:
        return None
    return placements


def validate(
    *,
    parsed_answer: dict[str, Any],
    gold_answer: dict[str, Any],
    task: dict[str, Any],
    project_root: Path | None = None,
) -> Verdict:
    """Score the model's placements via pixel-level IoU against the target mask.

    `parsed_answer` and `gold_answer` are both `{"placements": [...]}` per
    docs/PROMPT_SKELETON.md §3.1. `task` is the full level JSON (or a path string
    accepted by the engine).
    """
    placements = _placements_from_answer(parsed_answer)
    if placements is None:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["placements_missing_or_empty"],
            detail={},
        )

    # The legacy engine accepts a level JSON path, so we either have a path or we
    # write the level dict to a temp location. Most callers pass the level dict;
    # convert it to a path-on-disk via the dataset_io flow if needed.
    level_path: Path | None = None
    if isinstance(task, dict) and "level_path" in task and task["level_path"]:
        level_path = Path(task["level_path"])
    elif isinstance(task, dict):
        # Find the on-disk level file via the (project_root, ID) convention.
        if project_root is not None and task.get("ID"):
            candidate = project_root / "data" / "levels" / f"{task['ID']}.json"
            if candidate.exists():
                level_path = candidate
    elif isinstance(task, (str, Path)):
        level_path = Path(task)

    if level_path is None or not level_path.exists():
        # Fall back to writing the dict to a tempfile so the engine can read it.
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(task, tmp, ensure_ascii=False)
            level_path = Path(tmp.name)

    model_dsl = placements_to_dsl(placements)
    engine_result = evaluate_with_project_engine(level_path, model_dsl)

    is_pattern_matched = bool(engine_result.get("is_pattern_matched", False))
    iou = float(engine_result.get("pattern_iou", 0.0))
    validation_errors = list(engine_result.get("validation_errors", []) or [])
    evaluation_status = engine_result.get("evaluation_status", "")

    if evaluation_status == "invalid_output":
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["engine_invalid_output", *validation_errors],
            detail={"engine_result": engine_result, "gold_answer": gold_answer},
        )

    if is_pattern_matched:
        return Verdict(
            status="passed",
            score=1.0,
            errors=[],
            detail={"engine_result": engine_result, "gold_answer": gold_answer},
        )

    errors: list[str] = []
    for raw_error in validation_errors:
        # Map the engine's free-text validation errors into short identifiers.
        text = str(raw_error).lower()
        if "unknown shape" in text:
            errors.append("unknown_shape")
        elif "unknown vertex" in text:
            errors.append("unknown_vertex")
        elif "reused" in text or "only be used once" in text:
            errors.append("shape_reused")
        elif "no valid operation-code lines" in text:
            errors.append("engine_invalid_output")
        else:
            errors.append("engine_validation_error")
    if not errors:
        errors.append("pattern_mismatch")

    return Verdict(
        status="failed",
        score=round(iou, 6),
        errors=errors,
        detail={"engine_result": engine_result, "gold_answer": gold_answer},
    )
