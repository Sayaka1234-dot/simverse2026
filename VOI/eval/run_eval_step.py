from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from engine_interface import evaluate_with_project_engine
from eval_common import (
    DEFAULT_JSON_PATH,
    DEFAULT_LEVELS_DIR,
    build_multimodal_content,
    extract_text_content,
    get_invalid_output_reasons,
    list_level_json_paths,
    load_level_json,
    load_level_targets_json,
    print_invalid_output_skip,
    print_model_output_debug,
    save_result_json,
    utc_timestamp,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent
DEFAULT_STEP_MODEL_NAME = os.getenv("STEP_MODEL_NAME", "step-1o-turbo-vision")
DEFAULT_STEP_BASE_URL = os.getenv("STEP_BASE_URL", "https://api.stepfun.com/v1")
DEFAULT_STEP_API_KEY = os.getenv("STEP_API_KEY", "3ZYoEQ57sctL5wZezPEiOYZ25lYRQZOEzkdAYJ1yzRSETWLOp5zE0JVZQSlZQW6N3")
DEFAULT_STEP_TIMEOUT_SECONDS = float(
    os.getenv("STEP_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_SECONDS", "900"))
)
DEFAULT_STEP_MAX_REQUESTS_PER_MINUTE = int(os.getenv("STEP_MAX_REQUESTS_PER_MINUTE", "10"))
DEFAULT_STEP_TRUST_ENV = os.getenv(
    "STEP_TRUST_ENV",
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

try:
    from openai import APIConnectionError, APITimeoutError
except ModuleNotFoundError:  # pragma: no cover
    APIConnectionError = APITimeoutError = Exception


_LAST_STEP_REQUEST_STARTED_AT: float | None = None


def build_argument_parser(default_level: str = "level001") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run single-level or batch evaluation for Text-VOI with Step models."
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
        default=None,
        help="Directory used to store result JSON files. Default: results/<model_name>.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional batch limit.")
    parser.add_argument("--model", default=DEFAULT_STEP_MODEL_NAME)
    parser.add_argument("--base-url", default=DEFAULT_STEP_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_STEP_API_KEY)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_STEP_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--trust-env",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_STEP_TRUST_ENV,
        help="Whether to trust proxy settings from environment variables.",
    )
    parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=DEFAULT_STEP_MAX_REQUESTS_PER_MINUTE,
        help="Throttle Step requests to stay within the account RPM limit.",
    )
    parser.add_argument("--max-tokens", type=int, default=10000)
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Automatic retry count for suspected truncated outputs.",
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


def resolve_results_dir(args: argparse.Namespace) -> Path:
    if args.results_dir is not None:
        return args.results_dir.resolve()
    return (EVAL_ROOT / "results" / args.model).resolve()


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


def build_step_client(
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    trust_env: bool,
):
    from openai import OpenAI

    timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds, read=timeout_seconds)
    http_client = httpx.Client(timeout=timeout, trust_env=trust_env)
    client = OpenAI(base_url=base_url, api_key=api_key, http_client=http_client)
    return client, http_client


def reset_step_rate_limit_state() -> None:
    global _LAST_STEP_REQUEST_STARTED_AT
    _LAST_STEP_REQUEST_STARTED_AT = None


def enforce_step_request_rate_limit(max_requests_per_minute: int) -> float:
    global _LAST_STEP_REQUEST_STARTED_AT

    safe_rpm = max(1, int(max_requests_per_minute))
    min_interval_seconds = 60.0 / safe_rpm
    now = time.perf_counter()

    if _LAST_STEP_REQUEST_STARTED_AT is None:
        _LAST_STEP_REQUEST_STARTED_AT = now
        return 0.0

    elapsed_seconds = now - _LAST_STEP_REQUEST_STARTED_AT
    wait_seconds = max(0.0, min_interval_seconds - elapsed_seconds)
    if wait_seconds > 0:
        time.sleep(wait_seconds)
        now = time.perf_counter()

    _LAST_STEP_REQUEST_STARTED_AT = now
    return wait_seconds


def print_request_config(args: argparse.Namespace, results_dir: Path) -> None:
    print("=== Step Request Config ===")
    print("provider        : stepfun-openai-compatible")
    print(f"base_url        : {args.base_url}")
    print(f"model           : {args.model}")
    print(f"timeout_seconds : {args.timeout_seconds}")
    print(f"trust_env       : {args.trust_env}")
    print("thinking_mode   : provider-default (reasoning allowed)")
    print(f"max_rpm         : {args.max_requests_per_minute}")
    print(f"max_tokens      : {args.max_tokens}")
    print(f"max_retries     : {args.max_retries}")
    print(f"results_dir     : {results_dir}")
    print()


def normalize_candidate_line(raw_line: str) -> str:
    candidate = raw_line.strip().strip("`")
    candidate = re.sub(r"^\s*(?:[-*]\s+|\d+[.)]\s+)", "", candidate)
    return candidate.strip()


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


def extract_operation_code_lines(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        candidate = normalize_candidate_line(raw_line)
        if FULL_COMMAND_LINE_PATTERN.fullmatch(candidate):
            lines.append(candidate)
    return "\n".join(lines)


def flatten_stream_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(flatten_stream_text(item))
        return "".join(parts)
    text = getattr(value, "text", None)
    if text is not None:
        return str(text)
    return str(value)


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

    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": build_system_message(),
            },
            {
                "role": "user",
                "content": content,
            },
        ],
        "stream": True,
        "max_tokens": max_tokens,
    }

    response = client.chat.completions.create(**request_kwargs)

    output_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason = None
    response_id = None
    response_model = model_name

    for chunk in response:
        response_id = getattr(chunk, "id", response_id)
        response_model = getattr(chunk, "model", response_model)
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", finish_reason)
        delta = getattr(choice, "delta", None)
        if delta is None:
            continue

        reasoning_content = flatten_stream_text(
            getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
        )
        if reasoning_content:
            reasoning_parts.append(reasoning_content)

        content_text = flatten_stream_text(getattr(delta, "content", None))
        if content_text:
            output_parts.append(content_text)

    raw_content_text = "".join(output_parts).strip()
    final_text = extract_operation_code_lines(raw_content_text)
    reasoning_text = "".join(reasoning_parts).strip()

    return {
        "text": extract_text_content(final_text),
        "raw_content_text": raw_content_text,
        "finish_reason": finish_reason,
        "response_id": response_id,
        "response_model": response_model,
        "thinking_request_mode": "provider-default",
        "reasoning_char_count": len(reasoning_text),
        "reasoning_content": reasoning_text,
        "request_kwargs": request_kwargs,
    }


def request_operation_code_with_retry(
    client,
    level_path: Path,
    level_data: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    total_attempts = max(0, args.max_retries) + 1
    last_completion: dict[str, Any] | None = None
    total_request_duration = 0.0
    total_rate_limit_wait_seconds = 0.0

    for attempt_index in range(1, total_attempts + 1):
        retry_note = None
        if attempt_index > 1:
            retry_note = (
                "Your previous response seems to be truncated. Please answer again.\n"
                "You may still reason if needed, but make sure the final answer ends with complete operation-code lines.\n"
                "Each final operation-code line must end with a right bracket ]."
            )

        try:
            rate_limit_wait_seconds = enforce_step_request_rate_limit(
                args.max_requests_per_minute
            )
            total_rate_limit_wait_seconds += rate_limit_wait_seconds
            if rate_limit_wait_seconds > 0:
                print(
                    f"[Throttle][Step] {level_path.stem}: "
                    f"waiting {rate_limit_wait_seconds:.3f}s to respect "
                    f"{args.max_requests_per_minute} RPM."
                )
            request_started_at = time.perf_counter()
            completion = request_operation_completion(
                client=client,
                level_path=level_path,
                level_data=level_data,
                model_name=args.model,
                max_tokens=args.max_tokens,
                retry_note=retry_note,
            )
            request_duration_seconds = time.perf_counter() - request_started_at
        except (APITimeoutError, APIConnectionError, Exception):
            raise

        total_request_duration += request_duration_seconds
        suspected_truncated = is_suspected_truncated_output(completion["text"])
        completion["suspected_truncated_output"] = suspected_truncated
        completion["attempt_count"] = attempt_index
        completion["request_duration_seconds"] = round(total_request_duration, 6)
        completion["rate_limit_wait_seconds"] = round(total_rate_limit_wait_seconds, 6)
        last_completion = completion

        print(
            f"Attempt {attempt_index}/{total_attempts}: "
            f"finish_reason={completion.get('finish_reason')} "
            f"suspected_truncated={suspected_truncated} "
            f"rate_limit_wait={rate_limit_wait_seconds:.3f} "
            f"request_seconds={request_duration_seconds:.3f}"
        )

        if not suspected_truncated:
            return completion

        if attempt_index < total_attempts:
            print(
                f"[Retry][Truncation] {level_path.stem}: "
                f"retrying because the output looks incomplete."
            )

    return last_completion if last_completion is not None else {
        "text": "",
        "raw_content_text": "",
        "finish_reason": None,
        "response_id": None,
        "response_model": args.model,
        "thinking_request_mode": "provider-default",
        "reasoning_char_count": 0,
        "reasoning_content": "",
        "request_kwargs": {},
        "suspected_truncated_output": True,
        "attempt_count": total_attempts,
        "request_duration_seconds": round(total_request_duration, 6),
        "rate_limit_wait_seconds": round(total_rate_limit_wait_seconds, 6),
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
    model_output = completion_data["text"]
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
            "provider": "stepfun-openai-compatible",
            "model_family": "step",
            "model_name": args.model,
            "base_url": args.base_url,
            "timeout_seconds": args.timeout_seconds,
            "trust_env": args.trust_env,
            "thinking_enabled": True,
            "max_requests_per_minute": args.max_requests_per_minute,
            "max_tokens": args.max_tokens,
        },
        "completion": {
            "used_model_name": completion_data.get("response_model"),
            "response_id": completion_data.get("response_id"),
            "finish_reason": completion_data.get("finish_reason"),
            "suspected_truncated_output": completion_data.get("suspected_truncated_output"),
            "attempt_count": completion_data.get("attempt_count"),
            "request_duration_seconds": completion_data.get("request_duration_seconds"),
            "rate_limit_wait_seconds": completion_data.get("rate_limit_wait_seconds", 0.0),
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
    results_dir: Path,
) -> dict[str, Any] | None:
    _, level_data = load_level_json(level_path)
    print(f"=== Evaluating {level_path.stem} with Step ===")
    level_started_at = time.perf_counter()

    try:
        completion = request_operation_code_with_retry(
            client=client,
            level_path=level_path,
            level_data=level_data,
            args=args,
        )
        print_model_output_debug(
            level_id=level_path.stem,
            provider_label="Step",
            model_output=completion.get("text"),
            raw_model_output=completion.get("raw_content_text"),
            reasoning_content=completion.get("reasoning_content"),
        )
        model_output = completion["text"]
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
        engine_result = evaluate_with_project_engine(level_path, model_output)
        engine_evaluation_seconds = time.perf_counter() - engine_started_at
        timing_data = {
            "model_response_seconds": round(
                float(completion.get("request_duration_seconds", 0.0) or 0.0), 6
            ),
            "engine_evaluation_seconds": round(engine_evaluation_seconds, 6),
            "total_level_seconds": round(time.perf_counter() - level_started_at, 6),
        }
        if get_invalid_output_reasons(engine_result):
            print_invalid_output_skip(
                level_path.stem,
                engine_result,
                model_output=completion.get("text"),
                raw_model_output=completion.get("raw_content_text"),
            )
            return None
        result_payload = build_result_payload(
            level_path,
            level_data,
            completion,
            engine_result,
            args,
            timing_data,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[Skip][RuntimeError] {level_path.stem}: {type(exc).__name__}: {exc}")
        print("No result file will be written for this level.\n")
        return None

    result_path = save_result_json(level_path, result_payload, results_dir)
    print(f"Result saved: {result_path}")
    print(
        json.dumps(
            {
                "level_id": result_payload["level_id"],
                "evaluation_status": result_payload["evaluation_status"],
                "is_pattern_matched": result_payload["is_pattern_matched"],
                "pattern_iou": result_payload["pattern_iou"],
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
    print("=== Step Batch Summary ===")
    print(
        json.dumps(
            {
                "total_requested_levels": total_requested,
                "saved_result_levels": len(results),
                "skipped_runtime_error_levels": skipped_runtime_error_levels,
                "matched_levels": matched,
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

    if not args.api_key or args.api_key == "YOUR_STEPFUN_APIKEY":
        raise SystemExit("未设置 STEP_API_KEY，无法调用 Step 模型。")

    level_paths = select_level_paths(args)
    results_dir = resolve_results_dir(args)
    results_dir.mkdir(parents=True, exist_ok=True)
    print_request_config(args, results_dir)

    client, http_client = build_step_client(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout_seconds=args.timeout_seconds,
        trust_env=args.trust_env,
    )

    try:
        results: list[dict[str, Any]] = []
        skipped_runtime_error_levels = 0
        for level_path in level_paths:
            result_path = results_dir / f"{level_path.stem}.json"
            if args.skip_existing and result_path.exists():
                print(f"Skip existing result: {result_path}")
                continue

            result = evaluate_one_level(client, level_path, args, results_dir)
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
                        "model_response_seconds": results[0].get("timing", {}).get("model_response_seconds"),
                        "result_path": str(results_dir / f"{level_paths[0].stem}.json"),
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
