from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from engine_interface import evaluate_with_project_engine
from eval_common import (
    build_client,
    build_multimodal_content,
    extract_reasoning_content,
    extract_text_content,
    get_invalid_output_reasons,
    list_level_json_paths,
    load_level_json,
    load_level_targets_json,
    print_invalid_output_result,
    print_model_output_debug,
    save_result_json,
    utc_timestamp,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent
DEFAULT_QWEN_OPEN_MODEL_NAME = os.getenv("QWEN_OPEN_MODEL_NAME", "Qwen/Qwen3.5-397B-A17B")
DEFAULT_LEVELS_DIR = PROJECT_ROOT / "levels"
DEFAULT_RESULTS_DIR = EVAL_ROOT / "results" / DEFAULT_QWEN_OPEN_MODEL_NAME
DEFAULT_JSON_PATH = DEFAULT_LEVELS_DIR / "level001.json"
DEFAULT_QWEN_OPEN_BASE_URL = os.getenv(
    "QWEN_OPEN_BASE_URL",
    os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
)
DEFAULT_QWEN_OPEN_API_KEY = os.getenv(
    "QWEN_OPEN_API_KEY",
    os.getenv("SILICONFLOW_API_KEY", ""),
)
DEFAULT_QWEN_OPEN_TIMEOUT_SECONDS = float(
    os.getenv("QWEN_OPEN_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_SECONDS", "900"))
)
DEFAULT_QWEN_OPEN_TRUST_ENV = os.getenv(
    "QWEN_OPEN_TRUST_ENV",
    os.getenv("OPENAI_TRUST_ENV", "false"),
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


FULL_COMMAND_LINE_PATTERN = re.compile(
    r"^\s*[A-Za-z][\w-]*\s+(?:0|90|180|270)\s+V\d+\s+\[\s*-?\d+\s*,\s*-?\d+\s*\]\s*$"
)


def resolve_default_max_tokens(model_name: str) -> int:
    return 10000


def resolve_default_max_retries(model_name: str) -> int:
    return 1


def build_argument_parser(default_level: str = "level001") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run single-level or batch evaluation for Text-VOI with open-source Qwen models."
    )
    parser.add_argument(
        "--level",
        default=default_level,
        help="Single level id or json path. Ignored when --all is provided.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all level*.json files under the levels directory.",
    )
    parser.add_argument(
        "--level-list-json",
        type=Path,
        default=None,
        help="Optional JSON file containing a random/custom level list. Overrides --all and --level when provided.",
    )
    parser.add_argument(
        "--levels-dir",
        type=Path,
        default=DEFAULT_LEVELS_DIR,
        help="Directory that stores level JSON files.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory used to store result JSON files.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional batch limit.")
    parser.add_argument("--model", default=DEFAULT_QWEN_OPEN_MODEL_NAME)
    parser.add_argument("--base-url", default=DEFAULT_QWEN_OPEN_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_QWEN_OPEN_API_KEY)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_QWEN_OPEN_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--trust-env",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_QWEN_OPEN_TRUST_ENV,
        help="Whether to trust proxy settings from environment variables.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum output tokens. Default: 10000.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Automatic retry count for suspected truncated outputs. Default: 1.",
    )
    parser.add_argument(
        "--fallback-model",
        default=None,
        help="Optional fallback model used after truncation retries are exhausted.",
    )
    parser.add_argument(
        "--show-reference",
        action="store_true",
        help="Print the reference solution after each single-level run.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip levels whose result JSON already exists.",
    )
    return parser


def select_level_paths(args: argparse.Namespace) -> list[Path]:
    if args.level_list_json is not None:
        _, level_targets = load_level_targets_json(args.level_list_json)
        return [
            load_level_json(level_target, levels_dir=args.levels_dir)[0]
            for level_target in level_targets
        ]

    if args.all:
        level_paths = list_level_json_paths(args.levels_dir)
        if args.limit is not None:
            level_paths = level_paths[: args.limit]
        return level_paths

    level_target = args.level if args.level else DEFAULT_JSON_PATH
    level_path, _ = load_level_json(level_target, levels_dir=args.levels_dir)
    return [level_path]


def print_request_config(args: argparse.Namespace) -> None:
    print("=== Qwen Open Request Config ===")
    print("provider        : siliconflow-openai-compatible")
    print(f"base_url        : {args.base_url}")
    print(f"model           : {args.model}")
    print(f"fallback_model  : {args.fallback_model}")
    print(f"timeout_seconds : {args.timeout_seconds}")
    print(f"trust_env       : {args.trust_env}")
    print("thinking_mode   : provider-default (reasoning allowed)")
    print(f"max_tokens      : {args.max_tokens}")
    print(f"max_retries     : {args.max_retries}")
    print(f"results_dir     : {args.results_dir}")
    print()


def serialize_usage(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage

    payload: dict[str, Any] = {}
    for field_name in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_tokens_details",
        "completion_tokens_details",
    ):
        value = getattr(usage, field_name, None)
        if value is None:
            continue
        if hasattr(value, "model_dump"):
            payload[field_name] = value.model_dump()
        else:
            payload[field_name] = value
    return payload or None


def normalize_candidate_line(raw_line: str) -> str:
    candidate = raw_line.strip().strip("`")
    candidate = re.sub(r"^\s*(?:[-*]\s+|\d+[.)]\s+)", "", candidate)
    return candidate.strip()


def extract_operation_code_lines(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        candidate = normalize_candidate_line(raw_line)
        if FULL_COMMAND_LINE_PATTERN.fullmatch(candidate):
            lines.append(candidate)
    return "\n".join(lines)


def is_suspected_truncated_output(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True

    lines = []
    for raw_line in stripped.splitlines():
        candidate = normalize_candidate_line(raw_line)
        if not candidate or candidate.startswith("```"):
            continue
        lines.append(candidate)

    if not lines:
        return True

    if not lines[-1].endswith("]"):
        return True

    return FULL_COMMAND_LINE_PATTERN.fullmatch(lines[-1]) is None


def build_attempt_plan(args: argparse.Namespace) -> list[str]:
    primary_attempts = max(0, args.max_retries) + 1
    plan = [args.model] * primary_attempts
    if args.fallback_model:
        plan.append(args.fallback_model)
    return plan


def request_operation_completion(
    client,
    level_path: Path,
    level_data: dict[str, Any],
    model_name: str,
    max_tokens: int,
    retry_note: str | None = None,
) -> dict[str, Any]:
    from eval_common import build_system_message

    content = build_multimodal_content(level_path, level_data)
    if retry_note:
        content = [
            *content,
            {"type": "text", "text": retry_note},
        ]

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": build_system_message(),
            },
            {
                "role": "user",
                "content": content,
            }
        ],
        max_tokens=max_tokens,
    )

    message = response.choices[0].message
    raw_content_text = extract_text_content(getattr(message, "content", None))
    reasoning_content = extract_reasoning_content(message)
    final_text = extract_operation_code_lines(raw_content_text)

    return {
        "text": final_text,
        "raw_content_text": raw_content_text,
        "finish_reason": getattr(response.choices[0], "finish_reason", None),
        "usage": serialize_usage(getattr(response, "usage", None)),
        "response_id": getattr(response, "id", None),
        "response_model": getattr(response, "model", model_name),
        "thinking_request_mode": "provider-default",
        "reasoning_char_count": len(reasoning_content),
        "reasoning_content": reasoning_content,
    }


def request_operation_code_with_retry(
    client,
    level_path: Path,
    level_data: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    from openai import APIConnectionError, APITimeoutError

    attempt_plan = build_attempt_plan(args)
    attempt_records: list[dict[str, Any]] = []
    last_completion: dict[str, Any] | None = None
    total_request_duration = 0.0

    for attempt_index, attempt_model_name in enumerate(attempt_plan, start=1):
        is_fallback_attempt = (
            args.fallback_model is not None and attempt_model_name == args.fallback_model
        )
        retry_note = None
        if attempt_index > 1:
            retry_note = (
                "Your previous response seems to be truncated. Please answer again.\n"
                "You may still reason if needed, but make sure the final answer ends with complete operation-code lines.\n"
                "Each final operation-code line must end with a right bracket ]."
            )

        try:
            request_started_at = time.perf_counter()
            completion = request_operation_completion(
                client=client,
                level_path=level_path,
                level_data=level_data,
                model_name=attempt_model_name,
                max_tokens=args.max_tokens,
                retry_note=retry_note,
            )
            request_duration_seconds = time.perf_counter() - request_started_at
        except (APITimeoutError, APIConnectionError, Exception):
            raise

        total_request_duration += request_duration_seconds
        suspected_truncation = is_suspected_truncated_output(completion["text"]) or (
            str(completion.get("finish_reason") or "").lower() == "length"
        )

        attempt_record = {
            "attempt_index": attempt_index,
            "model_name": attempt_model_name,
            "is_fallback_model": is_fallback_attempt,
            "finish_reason": completion.get("finish_reason"),
            "usage": completion.get("usage"),
            "response_id": completion.get("response_id"),
            "response_model": completion.get("response_model"),
            "output_char_count": len(completion["text"]),
            "suspected_truncated_output": suspected_truncation,
            "request_duration_seconds": round(request_duration_seconds, 6),
        }
        attempt_records.append(attempt_record)
        last_completion = completion
        print(
            "Thinking payload: "
            f"requested_mode={completion.get('thinking_request_mode', 'provider-default')}"
        )

        if not suspected_truncation:
            break

    if last_completion is None:
        raise RuntimeError("No completion response was produced.")

    return {
        "model_output": last_completion["text"],
        "raw_content_text": last_completion.get("raw_content_text", ""),
        "finish_reason": last_completion.get("finish_reason"),
        "usage": last_completion.get("usage"),
        "response_id": last_completion.get("response_id"),
        "response_model": last_completion.get("response_model"),
        "suspected_truncated_output": is_suspected_truncated_output(last_completion["text"]),
        "attempts": attempt_records,
        "attempt_count": len(attempt_records),
        "retried_for_truncation": len(attempt_records) > 1,
        "truncation_retry_count": max(0, len(attempt_records) - 1),
        "request_duration_seconds": round(total_request_duration, 6),
        "thinking_request_mode": last_completion.get("thinking_request_mode", "provider-default"),
        "reasoning_char_count": last_completion.get("reasoning_char_count", 0),
        "reasoning_content": last_completion.get("reasoning_content", ""),
    }


def build_result_payload(
    level_path: Path,
    level_data: dict[str, Any],
    completion_data: dict[str, Any],
    engine_result: dict[str, Any],
    args: argparse.Namespace,
    timing_data: dict[str, float],
) -> dict[str, Any]:
    meta = level_data.get("meta", {})
    model_output = completion_data["model_output"]
    return {
        "level_id": level_path.stem,
        "level_name": level_data.get("name"),
        "level_json_path": str(level_path),
        "difficulty_tier": meta.get("difficultyTier"),
        "difficulty_label": meta.get("difficultyLabel"),
        "required_shape_count": meta.get("requiredShapeCount"),
        "distractor_shape_count": meta.get("distractorShapeCount"),
        "shape_pool_complexity": meta.get("shapePoolComplexity"),
        "grid_size": level_data.get("gridSize"),
        "is_pattern_matched": engine_result.get("is_pattern_matched"),
        "pattern_iou": engine_result.get("pattern_iou"),
        "overlap_ratio": engine_result.get("overlap_ratio"),
        "reference_iou": engine_result.get("reference_iou"),
        "dice_score": engine_result.get("dice_score"),
        "evaluation_status": engine_result.get("evaluation_status"),
        "model_output": model_output,
        "reference_solution": level_data.get("solutionText"),
        "image_assets": level_data.get("imageAssets", {}),
        "model": {
            "provider": "siliconflow-openai-compatible",
            "model_family": "qwen-open",
            "model_name": args.model,
            "base_url": args.base_url,
            "timeout_seconds": args.timeout_seconds,
            "trust_env": args.trust_env,
            "thinking_enabled": True,
            "max_tokens": args.max_tokens,
            "fallback_model": args.fallback_model,
        },
        "completion": {
            "used_model_name": completion_data.get("response_model"),
            "response_id": completion_data.get("response_id"),
            "finish_reason": completion_data.get("finish_reason"),
            "usage": completion_data.get("usage"),
            "suspected_truncated_output": completion_data.get("suspected_truncated_output"),
            "attempt_count": completion_data.get("attempt_count"),
            "retried_for_truncation": completion_data.get("retried_for_truncation"),
            "truncation_retry_count": completion_data.get("truncation_retry_count"),
            "attempts": completion_data.get("attempts"),
            "request_duration_seconds": completion_data.get("request_duration_seconds"),
            "thinking_request_mode": completion_data.get("thinking_request_mode"),
            "raw_content_text": completion_data.get("raw_content_text", ""),
            "reasoning_char_count": completion_data.get("reasoning_char_count"),
            "reasoning_content": completion_data.get("reasoning_content", ""),
        },
        "timing": timing_data,
        "engine_result": engine_result,
        "saved_at_utc": utc_timestamp(),
    }


def evaluate_one_level(
    client,
    level_path: Path,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    from openai import APIConnectionError, APITimeoutError

    _, level_data = load_level_json(level_path)
    print(f"=== Evaluating {level_path.stem} with Qwen Open ===")
    level_started_at = time.perf_counter()

    try:
        completion_data = request_operation_code_with_retry(
            client=client,
            level_path=level_path,
            level_data=level_data,
            args=args,
        )
        print_model_output_debug(
            level_id=level_path.stem,
            provider_label="Qwen Open",
            model_output=completion_data.get("model_output"),
            raw_model_output=completion_data.get("raw_content_text"),
            reasoning_content=completion_data.get("reasoning_content"),
        )
    except APITimeoutError as exc:
        print(f"[Skip][Timeout] {level_path.stem}: {exc}")
        print("No result file will be written for this level.\n")
        return None
    except APIConnectionError as exc:
        print(f"[Skip][ConnectionError] {level_path.stem}: {exc}")
        print("No result file will be written for this level.\n")
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[Skip][RequestError] {level_path.stem}: {type(exc).__name__}: {exc}")
        print("No result file will be written for this level.\n")
        return None

    try:
        engine_started_at = time.perf_counter()
        engine_result = evaluate_with_project_engine(level_path, completion_data["model_output"])
        engine_evaluation_seconds = time.perf_counter() - engine_started_at
        timing_data = {
            "model_response_seconds": round(
                float(completion_data.get("request_duration_seconds", 0.0) or 0.0), 6
            ),
            "engine_evaluation_seconds": round(engine_evaluation_seconds, 6),
            "total_level_seconds": round(time.perf_counter() - level_started_at, 6),
        }
        if get_invalid_output_reasons(engine_result):
            print_invalid_output_result(
                level_path.stem,
                engine_result,
                model_output=completion_data.get("model_output"),
                raw_model_output=completion_data.get("raw_content_text"),
            )
        result_payload = build_result_payload(
            level_path=level_path,
            level_data=level_data,
            completion_data=completion_data,
            engine_result=engine_result,
            args=args,
            timing_data=timing_data,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[Skip][RuntimeError] {level_path.stem}: {type(exc).__name__}: {exc}")
        print("No result file will be written for this level.\n")
        return None

    result_path = save_result_json(level_path, result_payload, args.results_dir)
    print(f"Result saved: {result_path}")
    print(
        json.dumps(
            {
                "level_id": result_payload["level_id"],
                "evaluation_status": result_payload["evaluation_status"],
                "is_pattern_matched": result_payload["is_pattern_matched"],
                "pattern_iou": result_payload["pattern_iou"],
                "finish_reason": result_payload["completion"]["finish_reason"],
                "attempt_count": result_payload["completion"]["attempt_count"],
                "suspected_truncated_output": result_payload["completion"]["suspected_truncated_output"],
                "model_response_seconds": result_payload["timing"]["model_response_seconds"],
                "total_level_seconds": result_payload["timing"]["total_level_seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print()

    if args.show_reference and not args.all:
        print("=== Reference Solution ===")
        print(level_data.get("solutionText", "").strip())
        print()

    return result_payload


def print_batch_summary(
    results: list[dict[str, Any]],
    total_requested: int,
    skipped_runtime_error_levels: int,
) -> None:
    matched = sum(1 for item in results if item.get("is_pattern_matched"))
    suspected_truncation_results = sum(
        1 for item in results if item.get("completion", {}).get("suspected_truncated_output")
    )
    avg_iou = (
        sum(float(item.get("pattern_iou", 0.0) or 0.0) for item in results) / len(results)
        if results
        else 0.0
    )
    avg_model_response_seconds = (
        sum(
            float(item.get("timing", {}).get("model_response_seconds", 0.0) or 0.0)
            for item in results
        )
        / len(results)
        if results
        else 0.0
    )
    print("=== Qwen Open Batch Summary ===")
    print(
        json.dumps(
            {
                "total_requested_levels": total_requested,
                "saved_result_levels": len(results),
                "skipped_runtime_error_levels": skipped_runtime_error_levels,
                "matched_levels": matched,
                "suspected_truncation_results": suspected_truncation_results,
                "average_pattern_iou": round(avg_iou, 6),
                "average_model_response_seconds": round(avg_model_response_seconds, 6),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print()


def main(default_level: str = "level001") -> int:
    parser = build_argument_parser(default_level=default_level)
    args = parser.parse_args()

    if args.max_tokens is None:
        args.max_tokens = resolve_default_max_tokens(args.model)
    if args.max_retries is None:
        args.max_retries = resolve_default_max_retries(args.model)

    if not args.api_key:
        raise SystemExit("未设置 QWEN_OPEN_API_KEY / SILICONFLOW_API_KEY，无法运行 Qwen Open 评测。")

    level_paths = select_level_paths(args)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    print_request_config(args)

    client, http_client = build_client(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout_seconds=args.timeout_seconds,
        trust_env=args.trust_env,
    )

    try:
        results: list[dict[str, Any]] = []
        skipped_runtime_error_levels = 0
        for level_path in level_paths:
            result_path = args.results_dir / f"{level_path.stem}.json"
            if args.skip_existing and result_path.exists():
                print(f"Skip existing result: {result_path}")
                continue

            result = evaluate_one_level(client, level_path, args)
            if result is None:
                skipped_runtime_error_levels += 1
                continue
            results.append(result)

        if args.all:
            print_batch_summary(results, len(level_paths), skipped_runtime_error_levels)
        elif results:
            print("=== Final Summary ===")
            print(
                json.dumps(
                    {
                        "level_id": results[0].get("level_id"),
                        "evaluation_status": results[0].get("evaluation_status"),
                        "is_pattern_matched": results[0].get("is_pattern_matched"),
                        "pattern_iou": results[0].get("pattern_iou"),
                        "finish_reason": results[0].get("completion", {}).get("finish_reason"),
                        "attempt_count": results[0].get("completion", {}).get("attempt_count"),
                        "model_response_seconds": results[0].get("timing", {}).get("model_response_seconds"),
                        "result_path": str(args.results_dir / f"{level_paths[0].stem}.json"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            print()
        else:
            print("=== Final Summary ===")
            print(
                json.dumps(
                    {
                        "level_id": level_paths[0].stem if level_paths else None,
                        "evaluation_status": "skipped_runtime_error",
                        "result_path": None,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            print()
    finally:
        http_client.close()

    return 0 if (args.all or results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
