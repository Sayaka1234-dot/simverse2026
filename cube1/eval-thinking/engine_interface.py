from __future__ import annotations

from typing import Any

from eval_common import ANSWER_FACE_ORDER, FaceAnswer, ModelAnswer, PuzzleTask


VALID_ROTATIONS = {0, 90, 180, 270}


def normalize_rotation(rotation: int) -> int:
    normalized = int(rotation) % 360
    if normalized not in VALID_ROTATIONS:
        raise ValueError(f"Rotation must be one of 0, 90, 180, 270, got {rotation}")
    return normalized


def evaluate_face(expected: FaceAnswer, predicted: FaceAnswer | None) -> dict[str, Any]:
    if predicted is None:
        return {
            "expected": {"patternId": expected.patternId, "rotation": expected.rotation},
            "predicted": None,
            "expected_unknown": expected.patternId == "?",
            "pattern_correct": False,
            "rotation_checked": expected.patternId != "?",
            "rotation_correct": False,
            "face_correct": False,
        }

    expected_rotation = normalize_rotation(expected.rotation)
    predicted_rotation = normalize_rotation(predicted.rotation)
    expected_unknown = expected.patternId == "?"
    pattern_correct = predicted.patternId == expected.patternId

    if expected_unknown:
        rotation_checked = False
        rotation_correct = predicted.patternId == "?"
        face_correct = predicted.patternId == "?"
    else:
        rotation_checked = True
        rotation_correct = pattern_correct and predicted_rotation == expected_rotation
        face_correct = pattern_correct and rotation_correct

    return {
        "expected": {"patternId": expected.patternId, "rotation": expected_rotation},
        "predicted": {"patternId": predicted.patternId, "rotation": predicted_rotation},
        "expected_unknown": expected_unknown,
        "pattern_correct": pattern_correct,
        "rotation_checked": rotation_checked,
        "rotation_correct": rotation_correct,
        "face_correct": face_correct,
    }


def evaluate_with_project_engine(task: PuzzleTask, answer: ModelAnswer) -> dict[str, Any]:
    if task.answer is None:
        return {
            "evaluation_status": "missing_answer",
            "is_fully_correct": False,
            "face_results": {},
        }

    face_results: dict[str, Any] = {}
    total_face_count = len(ANSWER_FACE_ORDER)
    determined_face_count = 0
    unknown_face_count = 0
    correct_face_count = 0
    correct_pattern_count = 0
    correct_pattern_and_rotation_count = 0
    correct_determined_face_count = 0
    correct_unknown_face_count = 0

    for face_key in ANSWER_FACE_ORDER:
        expected = task.answer[face_key]
        predicted = answer.answer.get(face_key)
        result = evaluate_face(expected, predicted)
        face_results[face_key] = result

        if result["expected_unknown"]:
            unknown_face_count += 1
            if result["face_correct"]:
                correct_unknown_face_count += 1
        else:
            determined_face_count += 1
            if result["pattern_correct"]:
                correct_pattern_count += 1
            if result["rotation_correct"]:
                correct_pattern_and_rotation_count += 1
            if result["face_correct"]:
                correct_determined_face_count += 1

        if result["face_correct"]:
            correct_face_count += 1

    return {
        "evaluation_status": "ok",
        "is_fully_correct": correct_face_count == total_face_count,
        "total_face_count": total_face_count,
        "correct_face_count": correct_face_count,
        "incorrect_face_count": total_face_count - correct_face_count,
        "determined_face_count": determined_face_count,
        "correct_determined_face_count": correct_determined_face_count,
        "unknown_face_count": unknown_face_count,
        "correct_unknown_face_count": correct_unknown_face_count,
        "correct_pattern_count": correct_pattern_count,
        "correct_pattern_and_rotation_count": correct_pattern_and_rotation_count,
        "correct_rotation_count": correct_pattern_and_rotation_count,
        "overall_face_accuracy": round(correct_face_count / total_face_count, 6) if total_face_count else 0.0,
        "determined_face_accuracy": round(correct_determined_face_count / determined_face_count, 6)
        if determined_face_count else 0.0,
        "unknown_face_accuracy": round(correct_unknown_face_count / unknown_face_count, 6)
        if unknown_face_count else 0.0,
        "pattern_accuracy": round(correct_pattern_count / determined_face_count, 6) if determined_face_count else 0.0,
        "pattern_and_rotation_accuracy": round(correct_pattern_and_rotation_count / determined_face_count, 6)
        if determined_face_count else 0.0,
        "rotation_accuracy": round(correct_pattern_and_rotation_count / determined_face_count, 6)
        if determined_face_count else 0.0,
        "face_results": face_results,
    }
