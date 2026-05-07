from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from eval_common import (
    build_argument_parser,
    build_openai_client,
    build_system_message,
    build_video_content,
    extract_stream_delta_output_parts,
    finalize_stream_output_parts,
    run_eval_loop,
)


DEFAULT_MODEL_NAME = os.getenv("STEP_MODEL_NAME", "step-1o-turbo-vision")
DEFAULT_BASE_URL = os.getenv("STEP_BASE_URL", "https://api.stepfun.com/v1")
DEFAULT_API_KEY = os.getenv("STEP_API_KEY", "3ZYoEQ57sctL5wZezPEiOYZ25lYRQZOEzkdAYJ1yzRSETWLOp5zE0JVZQSlZQW6N3")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("STEP_TIMEOUT_SECONDS", "600"))
DEFAULT_MAX_TOKENS = int(os.getenv("STEP_MAX_TOKENS", "10000"))
DEFAULT_TRUST_ENV = os.getenv("STEP_TRUST_ENV", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv("STEP_MIN_REQUEST_INTERVAL_SECONDS", "6.5"))

_LAST_REQUEST_STARTED_AT: float | None = None


def enforce_rate_limit(min_request_interval_seconds: float) -> float:
    global _LAST_REQUEST_STARTED_AT
    min_interval = max(0.0, float(min_request_interval_seconds))
    now = time.perf_counter()
    if _LAST_REQUEST_STARTED_AT is None:
        _LAST_REQUEST_STARTED_AT = now
        return 0.0
    wait_seconds = max(0.0, min_interval - (now - _LAST_REQUEST_STARTED_AT))
    if wait_seconds > 0:
        time.sleep(wait_seconds)
        now = time.perf_counter()
    _LAST_REQUEST_STARTED_AT = now
    return wait_seconds


def resolve_min_request_interval_seconds(args) -> float:
    max_requests_per_minute = getattr(args, "max_requests_per_minute", None)
    if max_requests_per_minute is not None:
        return 60.0 / max(1, int(max_requests_per_minute))
    explicit_interval = getattr(args, "min_request_interval_seconds", None)
    if explicit_interval is not None:
        return float(explicit_interval)
    return DEFAULT_MIN_REQUEST_INTERVAL_SECONDS


def request_completion(client: Any, item_path: Path, eval_item: dict[str, Any], args, retry_note: str | None) -> dict[str, Any]:
    waited = enforce_rate_limit(resolve_min_request_interval_seconds(args))
    started_at = time.perf_counter()
    thinking_mode = "provider-default-enabled" if args.thinking_enabled else "disabled"
    response = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": build_system_message()},
            {
                "role": "user",
                "content": build_video_content(
                    item_path,
                    eval_item,
                    retry_note=retry_note,
                    video_source=args.video_source,
                    video_part_type=args.video_part_type,
                    video_detail=args.video_detail,
                    video_max_frames=args.video_max_frames,
                    video_fps=args.video_fps,
                    video_frame_width=args.video_frame_width,
                    video_frame_quality=args.video_frame_quality,
                ),
            },
        ],
        max_tokens=args.max_tokens,
        stream=True,
    )

    output_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason = None
    response_id = None
    response_model = args.model
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
        text, reasoning = extract_stream_delta_output_parts(delta)
        if reasoning:
            reasoning_parts.append(reasoning)
        if text:
            output_parts.append(text)

    raw_text, reasoning_text = finalize_stream_output_parts(output_parts, reasoning_parts)
    return {
        "raw_content_text": raw_text,
        "finish_reason": finish_reason,
        "response_id": response_id,
        "response_model": response_model,
        "usage": None,
        "request_duration_seconds": round(time.perf_counter() - started_at, 6),
        "rate_limit_wait_seconds": round(waited, 6),
        "reasoning_char_count": len(reasoning_text),
        "reasoning_content": reasoning_text,
        "thinking_request_mode": thinking_mode,
    }


def build_step_argument_parser():
    parser = build_argument_parser(
        "Run Cut the Rope video-to-command evaluation with Step models.",
        default_model=DEFAULT_MODEL_NAME,
    )
    parser.add_argument(
        "--min-request-interval-seconds",
        type=float,
        default=DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
        help="Minimum delay between Step requests. Defaults to 6.5 seconds.",
    )
    parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=None,
        help="Backward-compatible rate limit option; overrides --min-request-interval-seconds when provided.",
    )
    parser.set_defaults(
        base_url=DEFAULT_BASE_URL,
        api_key=DEFAULT_API_KEY,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        trust_env=DEFAULT_TRUST_ENV,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    return parser


def main() -> int:
    parser = build_step_argument_parser()
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set STEP_API_KEY or pass --api-key.")

    client, http_client = build_openai_client(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout_seconds=args.timeout_seconds,
        trust_env=args.trust_env,
    )
    return run_eval_loop(
        args=args,
        client=client,
        close_client=http_client.close,
        provider="stepfun-compatible",
        request_completion=request_completion,
    )


if __name__ == "__main__":
    raise SystemExit(main())
