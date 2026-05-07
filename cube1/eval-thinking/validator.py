"""Cube1 validator. Implements docs/EVAL_CONTRACT.md §4.

Public entry point:
    validate(parsed_answer, gold_answer, task, project_root) -> Verdict

Cube1 supports partial credit: each of the 6 faces is scored independently and
the overall score is the fraction of faces that match (pattern + rotation, with
"?" sentinels treated as correct iff the gold also says "?").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine_interface import evaluate_with_project_engine
from eval_common import (
    ANSWER_FACE_ORDER,
    FaceAnswer,
    ModelAnswer,
    PuzzleTask,
)


@dataclass
class Verdict:
    status: str                    # "passed" | "failed" | "invalid_output"
    score: float                   # 0.0 .. 1.0 (fraction of faces correct)
    errors: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def _coerce_face_map(faces_payload: dict[str, Any]) -> dict[str, FaceAnswer]:
    coerced: dict[str, FaceAnswer] = {}
    for face_key in ANSWER_FACE_ORDER:
        if face_key not in faces_payload:
            raise KeyError(face_key)
        item = faces_payload[face_key]
        if not isinstance(item, dict):
            raise ValueError(face_key)
        coerced[face_key] = FaceAnswer.from_dict(item)
    return coerced


def validate(
    *,
    parsed_answer: dict[str, Any],
    gold_answer: dict[str, Any],
    task: dict[str, Any] | PuzzleTask,
    project_root: Path | None = None,
) -> Verdict:
    """Score the model's faces map against the gold faces map.

    `parsed_answer` and `gold_answer` are both `{"faces": {...}}` per
    docs/PROMPT_SKELETON.md §3.2.
    """
    if isinstance(task, dict):
        puzzle = PuzzleTask.from_dict(task)
    else:
        puzzle = task

    # Unwrap the new envelope, accept legacy bare face map too.
    parsed_faces_payload = parsed_answer.get("faces") if "faces" in parsed_answer else parsed_answer
    gold_faces_payload = gold_answer.get("faces") if "faces" in gold_answer else gold_answer

    if not isinstance(parsed_faces_payload, dict):
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["faces_missing"],
            detail={},
        )

    try:
        parsed_faces = _coerce_face_map(parsed_faces_payload)
    except KeyError as exc:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=[f"missing_face_{exc.args[0]}"],
            detail={},
        )
    except ValueError as exc:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=[f"bad_face_payload_{exc.args[0]}"],
            detail={},
        )

    if not isinstance(gold_faces_payload, dict):
        # Gold malformed — should never happen on shipped data, but guard anyway.
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["gold_answer_malformed"],
            detail={},
        )

    # The puzzle's `task.answer` is the gold; rebuild it from `gold_answer` for source-of-truth.
    try:
        gold_face_map = _coerce_face_map(gold_faces_payload)
    except (KeyError, ValueError):
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["gold_answer_malformed"],
            detail={},
        )

    # Reuse the existing engine: it expects `task.answer` to hold the gold map.
    puzzle_with_gold = PuzzleTask(
        sample_id=puzzle.sample_id,
        text_description=puzzle.text_description,
        net_layout=puzzle.net_layout,
        roll_sequence=puzzle.roll_sequence,
        observed_path_faces=puzzle.observed_path_faces,
        image_paths=puzzle.image_paths,
        answer=gold_face_map,
        metadata=puzzle.metadata,
    )
    model_answer = ModelAnswer(sample_id=puzzle.sample_id, answer=parsed_faces, raw_text="")
    engine_result = evaluate_with_project_engine(puzzle_with_gold, model_answer)

    correct = int(engine_result.get("correct_face_count", 0))
    total = int(engine_result.get("total_face_count", len(ANSWER_FACE_ORDER)))
    score = round(correct / total, 6) if total else 0.0
    is_full_pass = bool(engine_result.get("is_fully_correct", False))

    errors: list[str] = []
    if not is_full_pass:
        for face_key, face_result in engine_result.get("face_results", {}).items():
            if not face_result.get("face_correct", False):
                errors.append(f"face_wrong_{face_key}")

    return Verdict(
        status="passed" if is_full_pass else "failed",
        score=score,
        errors=errors,
        detail={"engine_result": engine_result, "gold_answer": gold_answer},
    )


