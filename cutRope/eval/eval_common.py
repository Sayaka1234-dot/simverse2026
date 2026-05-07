from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = EVAL_ROOT / "data"
DEFAULT_RESULTS_ROOT = EVAL_ROOT / "results"
DEFAULT_FRAME_CACHE_DIR = EVAL_ROOT / ".frame_cache"
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "900"))
DEFAULT_TRUST_ENV = os.getenv("OPENAI_TRUST_ENV", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_THINKING_ENABLED = os.getenv("CTR_EVAL_THINKING_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def sanitize_model_name_for_path(model_name: str | None) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(model_name or "").strip())
    sanitized = re.sub(r"_+", "_", sanitized).strip("._-")
    return sanitized or "unknown-model"


def build_model_results_dir(model_name: str | None) -> Path:
    return DEFAULT_RESULTS_ROOT / sanitize_model_name_for_path(model_name)


DEFAULT_RESULTS_DIR = build_model_results_dir(os.getenv("CTR_EVAL_MODEL_NAME", "openai-compatible"))


def resolve_results_dir(args: argparse.Namespace) -> Path:
    configured = getattr(args, "results_dir", None)
    if configured is not None:
        return Path(configured)
    return build_model_results_dir(getattr(args, "model", None))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_openai_client(
    base_url: str,
    api_key: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    trust_env: bool = DEFAULT_TRUST_ENV,
):
    import httpx
    from openai import OpenAI

    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 30.0), read=timeout_seconds)
    http_client = httpx.Client(timeout=timeout, trust_env=trust_env)
    client = OpenAI(base_url=base_url, api_key=api_key, http_client=http_client)
    return client, http_client


def encode_file(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def file_to_data_url(path: Path, fallback_mime_type: str = "application/octet-stream") -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or fallback_mime_type
    return f"data:{mime_type};base64,{encode_file(path)}"


def ensure_video_frame_paths(
    video_path: Path,
    *,
    max_frames: int = 8,
    frame_width: int = 960,
    quality: float = 0.85,
) -> list[Path]:
    video_path = video_path.resolve()
    stat = video_path.stat()
    cache_key = hashlib.sha1(
        f"{video_path}|{stat.st_size}|{stat.st_mtime_ns}|{max_frames}|{frame_width}|{quality}".encode("utf-8")
    ).hexdigest()[:16]
    output_dir = DEFAULT_FRAME_CACHE_DIR / f"{video_path.stem}-{cache_key}"
    expected_paths = [output_dir / f"frame-{index:02d}.jpg" for index in range(max_frames)]
    existing_paths = [path for path in expected_paths if path.exists()]
    if len(existing_paths) == max_frames:
        return existing_paths

    script_path = PROJECT_ROOT / "scripts" / "extract-video-frames.mjs"
    if not script_path.exists():
        raise FileNotFoundError(f"Video frame extractor script not found: {script_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "node",
        str(script_path),
        "--video",
        str(video_path),
        "--out",
        str(output_dir),
        "--max-frames",
        str(max_frames),
        "--width",
        str(frame_width),
        "--quality",
        str(quality),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Video frame extraction failed.\n"
            f"Command: {' '.join(command)}\n"
            f"stdout: {completed.stdout.strip()}\n"
            f"stderr: {completed.stderr.strip()}"
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Video frame extractor returned non-JSON output: {completed.stdout}") from exc

    frame_paths = [Path(path).resolve() for path in payload.get("frames", [])]
    if not frame_paths or any(not path.exists() for path in frame_paths):
        raise RuntimeError(f"Video frame extractor did not produce usable frames: {completed.stdout}")
    return frame_paths


def resolve_project_path(value: str | Path) -> Path:
    path_value = Path(value)
    if path_value.is_absolute():
        return path_value.resolve()
    return (PROJECT_ROOT / path_value).resolve()


def normalize_eval_item_target(target: str | Path, data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    if isinstance(target, Path):
        candidate = target
    else:
        text = str(target).strip()
        if text.endswith(".json") or any(sep in text for sep in ("/", "\\")):
            candidate = Path(text)
        else:
            candidate = data_dir / f"{text}.json"

    if not candidate.is_absolute():
        project_candidate = (PROJECT_ROOT / candidate).resolve()
        eval_candidate = (EVAL_ROOT / candidate).resolve()
        if project_candidate.exists():
            return project_candidate
        return eval_candidate
    return candidate.resolve()


def load_eval_item(target: str | Path, data_dir: Path = DEFAULT_DATA_DIR) -> tuple[Path, dict[str, Any]]:
    item_path = normalize_eval_item_target(target, data_dir=data_dir)
    if not item_path.exists():
        raise FileNotFoundError(f"Evaluation data JSON not found: {item_path}")
    return item_path, json.loads(item_path.read_text(encoding="utf-8"))


def list_eval_item_paths(data_dir: Path = DEFAULT_DATA_DIR) -> list[Path]:
    return sorted(path for path in data_dir.glob("*.json") if path.name != "manifest.json")


def load_eval_targets_json(level_list_json: str | Path) -> tuple[Path, list[str]]:
    list_path = Path(level_list_json)
    if not list_path.is_absolute():
        project_candidate = (PROJECT_ROOT / list_path).resolve()
        eval_candidate = (EVAL_ROOT / list_path).resolve()
        list_path = project_candidate if project_candidate.exists() else eval_candidate

    if not list_path.exists():
        raise FileNotFoundError(f"Level-list JSON not found: {list_path}")

    payload = json.loads(list_path.read_text(encoding="utf-8"))
    raw_levels = payload if isinstance(payload, list) else payload.get("levels")
    if not isinstance(raw_levels, list) or not raw_levels:
        raise ValueError("Level-list JSON must be a non-empty list or an object with a levels array.")

    levels = [str(item).strip() for item in raw_levels if str(item).strip()]
    if not levels:
        raise ValueError("Level-list JSON did not contain any usable level ids.")
    return list_path, levels


def save_result_json(item_path: Path, payload: dict[str, Any], results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / f"{item_path.stem}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_system_message() -> str:
    """SimVerse v1: delegates to prompts.build_system_prompt."""
    from prompts import build_system_prompt
    return build_system_prompt()


SUPPORTED_OBJECT_LABELS = {
    "target": "target",
    "star": "star",
    "candy": "candy",
    "left_candy": "left split candy",
    "right_candy": "right split candy",
    "grab_or_rope_anchor": "rope/grab",
    "bubble": "bubble",
    "pump": "pump",
    "gravity_button": "gravity switch",
}


def _format_supported_object_counts(counts: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, label in SUPPORTED_OBJECT_LABELS.items():
        value = counts.get(key)
        if isinstance(value, int) and value > 0:
            parts.append(f"{label}:{value}")
    return ", ".join(parts) or "no key objects covered by this simplified prompt were detected"


def _build_object_function_lines(counts: dict[str, Any], two_parts: bool) -> list[str]:
    lines = [
        "- Target: the level is won when the candy reaches the target monster's mouth. The target is usually fixed in place.",
    ]

    has_split_candy = two_parts or bool(counts.get("left_candy")) or bool(counts.get("right_candy"))
    if has_split_candy:
        lines.append(
            "- Split candy: the level may start with left_candy and right_candy halves. Before they merge, use left_candy_* and right_candy_* conditions. After the halves touch and merge, use candy_* for the complete candy."
        )
    else:
        lines.append(
            "- Candy: the candy is affected by gravity, ropes, bubbles, pumps, and other active objects. It must be delivered to the target."
        )

    if counts.get("grab_or_rope_anchor"):
        lines.append(
            "- Ropes and grabs: ropes constrain the candy or split candy movement. Use cut_rope N to cut rope N, or cut_rope N,M,K to cut multiple ropes at once. If a grab can move, use move_grab N X or move_grab N X Y."
        )
    if counts.get("star"):
        lines.append(
            "- Stars: candy or split candy collects a star by touching it. Prefer paths that collect stars, but stable completion is the first priority."
        )
    if counts.get("bubble"):
        lines.append(
            "- Bubbles: when candy enters a bubble it usually floats upward. Use pop_bubble N to pop bubble N. In split-candy levels, pop_bubble_left or pop_bubble_right can pop the bubble holding the corresponding half."
        )
    if counts.get("pump"):
        lines.append(
            "- Pumps: activating a pump pushes the candy or nearby objects. Use activate_pump N, optionally with times/every/until for repeated activation."
        )
    if counts.get("gravity_button"):
        lines.append(
            "- Gravity switch: use toggle_gravity to reverse or change gravity direction. This is often triggered after the candy crosses a coordinate threshold."
        )

    return lines


def build_prompt(eval_item: dict[str, Any]) -> str:
    """SimVerse v1: delegates to prompts.build_user_prompt."""
    from prompts import build_user_prompt
    return build_user_prompt(eval_item)


def select_video_info(eval_item: dict[str, Any], video_source: str = "mp4") -> dict[str, Any]:
    video_info = eval_item.get("video", {})
    if not isinstance(video_info, dict):
        raise ValueError("eval item is missing video metadata")

    source = (video_source or "mp4").strip().lower()
    variants = video_info.get("variants")
    if isinstance(variants, dict) and isinstance(variants.get(source), dict):
        selected = dict(variants[source])
        selected.setdefault("duration_seconds", video_info.get("duration_seconds"))
        selected.setdefault("fps", video_info.get("fps"))
        return selected
    return video_info


def build_video_content(
    item_path: Path,
    eval_item: dict[str, Any],
    retry_note: str | None = None,
    video_source: str = "mp4",
    video_part_type: str = "video_url",
    video_detail: str | None = None,
    video_max_frames: int | None = None,
    video_fps: float | None = None,
    video_frame_width: int = 960,
    video_frame_quality: float = 0.85,
) -> list[dict[str, Any]]:
    """SimVerse v1: delegates to prompts.build_messages and returns the user
    message's content array (legacy callers wrap their own role envelope around
    it)."""
    from prompts import build_messages
    messages = build_messages(
        item_path,
        eval_item,
        retry_note=retry_note,
        video_source=video_source,
        video_part_type=video_part_type,
        video_detail=video_detail,
        video_max_frames=video_max_frames,
        video_fps=video_fps,
        video_frame_width=video_frame_width,
        video_frame_quality=video_frame_quality,
    )
    user_msg = next((m for m in messages if m.get("role") == "user"), None)
    if user_msg is None or not isinstance(user_msg.get("content"), list):
        return []
    return list(user_msg["content"])


def extract_text_content(message_content: Any) -> str:
    if message_content is None:
        return ""
    if isinstance(message_content, str):
        return message_content.strip()
    if isinstance(message_content, dict):
        if "text" in message_content:
            return str(message_content.get("text", "")).strip()
        if "content" in message_content:
            return extract_text_content(message_content.get("content"))
        return ""
    if isinstance(message_content, list):
        chunks: list[str] = []
        for item in message_content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(str(item.get("text", "")))
                elif "text" in item:
                    chunks.append(str(item.get("text", "")))
                elif "content" in item:
                    chunks.append(extract_text_content(item.get("content")))
            else:
                text = getattr(item, "text", None)
                if text:
                    chunks.append(str(text))
        return "\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()
    return str(message_content).strip()


def flatten_rich_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(flatten_rich_text(item) for item in value)
    if isinstance(value, dict):
        if "text" in value:
            return str(value.get("text", ""))
        return "".join(flatten_rich_text(item) for item in value.values())
    text = getattr(value, "text", None)
    if text is not None:
        return str(text)
    return str(value)


def extract_reasoning_content(message: Any) -> str:
    if message is None:
        return ""
    candidates: list[Any] = []
    if isinstance(message, dict):
        candidates.extend(
            [
                message.get("reasoning_content"),
                message.get("reasoning"),
                message.get("thinking"),
                message.get("analysis"),
            ]
        )
    else:
        candidates.extend(
            [
                getattr(message, "reasoning_content", None),
                getattr(message, "reasoning", None),
                getattr(message, "thinking", None),
                getattr(message, "analysis", None),
            ]
        )
    return "\n".join(chunk for chunk in (flatten_rich_text(item).strip() for item in candidates) if chunk)


def _get_field(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def split_reasoning_from_raw_output(raw_text: str) -> tuple[str, str]:
    think_pattern = re.compile(r"<think>(.*?)</think>", re.IGNORECASE | re.DOTALL)
    reasoning_parts = [match.group(1).strip() for match in think_pattern.finditer(raw_text)]
    cleaned = think_pattern.sub("", raw_text).strip()
    return "\n".join(part for part in reasoning_parts if part), cleaned


def extract_message_output_parts(message: Any) -> tuple[str, str]:
    if message is None:
        return "", ""

    raw_text = extract_text_content(_get_field(message, "content"))
    reasoning_parts: list[str] = []
    for key in ("reasoning_content", "reasoning", "thinking", "analysis"):
        extracted = extract_text_content(_get_field(message, key))
        if extracted:
            reasoning_parts.append(extracted)

    reasoning_output = "\n".join(reasoning_parts).strip()
    if not reasoning_output and raw_text:
        reasoning_output, cleaned_raw = split_reasoning_from_raw_output(raw_text)
        if cleaned_raw:
            raw_text = cleaned_raw
    if not raw_text and reasoning_output:
        raw_text = reasoning_output

    return raw_text.strip(), reasoning_output.strip()


def extract_stream_text_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" or "text" in item:
                    parts.append(str(item.get("text", "")))
                elif "content" in item:
                    parts.append(extract_stream_text_content(item.get("content")))
            else:
                text = getattr(item, "text", None)
                if text is not None:
                    parts.append(str(text))
                    continue
                content = getattr(item, "content", None)
                if content is not None:
                    parts.append(extract_stream_text_content(content))
        return "".join(parts)
    if isinstance(value, dict):
        if "text" in value:
            return str(value.get("text", ""))
        if "content" in value:
            return extract_stream_text_content(value.get("content"))
        return flatten_rich_text(value)
    text = getattr(value, "text", None)
    if text is not None:
        return str(text)
    content = getattr(value, "content", None)
    if content is not None:
        return extract_stream_text_content(content)
    return str(value)


def extract_stream_delta_output_parts(delta: Any) -> tuple[str, str]:
    if delta is None:
        return "", ""

    raw_text = extract_stream_text_content(_get_field(delta, "content"))
    reasoning_parts: list[str] = []
    for key in ("reasoning_content", "reasoning", "thinking", "analysis"):
        extracted = extract_text_content(_get_field(delta, key))
        if extracted:
            reasoning_parts.append(extracted)
    return raw_text, "\n".join(reasoning_parts).strip()


def finalize_stream_output_parts(output_parts: list[str], reasoning_parts: list[str]) -> tuple[str, str]:
    raw_text = "".join(output_parts).strip()
    reasoning_output = "".join(reasoning_parts).strip()
    if not reasoning_output and raw_text:
        reasoning_output, cleaned_raw = split_reasoning_from_raw_output(raw_text)
        if cleaned_raw:
            raw_text = cleaned_raw
    if not raw_text and reasoning_output:
        raw_text = reasoning_output
    return raw_text.strip(), reasoning_output.strip()


def extract_json_object_text(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    match = JSON_OBJECT_PATTERN.search(stripped)
    if not match:
        raise ValueError("Model output does not contain a JSON object.")
    return match.group(0)


def parse_model_json(raw_text: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        parsed = json.loads(extract_json_object_text(raw_text))
    except Exception as exc:  # noqa: BLE001
        return None, [f"Could not parse model JSON: {type(exc).__name__}: {exc}"]
    if not isinstance(parsed, dict):
        return None, ["Model JSON root must be an object."]
    return parsed, []


def normalize_commands_from_model_json(parsed: dict[str, Any] | None) -> tuple[str, list[str]]:
    if parsed is None:
        return "", ["No parsed JSON object."]
    raw_commands = parsed.get("commands")
    if isinstance(raw_commands, list):
        commands = "\n".join(str(item).strip() for item in raw_commands if str(item).strip())
    elif isinstance(raw_commands, str):
        commands = raw_commands.strip()
    else:
        return "", ['Model JSON must contain "commands" as a string or list of strings.']

    if not commands:
        return "", ['Model JSON "commands" is empty.']
    if "wait_frames" in commands:
        return commands, ["wait_frames is not allowed in this benchmark version."]
    return commands, []


def is_suspected_truncated_output(raw_text: str) -> bool:
    parsed, errors = parse_model_json(raw_text)
    if errors or parsed is None:
        return True
    commands, command_errors = normalize_commands_from_model_json(parsed)
    return bool(command_errors or not commands)


def is_retryable_completion(completion: dict[str, Any]) -> bool:
    raw_text = str(completion.get("raw_content_text", ""))
    finish_reason = str(completion.get("finish_reason") or "").lower()
    return is_suspected_truncated_output(raw_text) or finish_reason == "length"


def build_attempt_model_names(args: argparse.Namespace) -> list[str]:
    primary_attempts = max(0, int(args.max_retries)) + 1
    model_names = [args.model] * primary_attempts
    fallback_model = getattr(args, "fallback_model", None)
    if fallback_model:
        model_names.append(str(fallback_model))
    return model_names


def clone_args_with_model(args: argparse.Namespace, model_name: str) -> argparse.Namespace:
    attempt_args = argparse.Namespace(**vars(args))
    attempt_args.model = model_name
    return attempt_args


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
        if value is not None:
            payload[field_name] = value.model_dump() if hasattr(value, "model_dump") else value
    return payload or None


def build_argument_parser(description: str, default_model: str, default_results_dir: Path | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--level", default="rope-000", help="Single eval item id or JSON path. Ignored by --all.")
    parser.add_argument("--all", action="store_true", help="Evaluate every JSON item under eval/data.")
    parser.add_argument("--level-list-json", type=Path, default=None, help="Optional JSON list of eval item ids.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=default_results_dir,
        help="Directory used to store result JSON files. Defaults to eval/results/<sanitized model name>.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default=default_model)
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--trust-env", action=argparse.BooleanOptionalAction, default=DEFAULT_TRUST_ENV)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--fallback-model", default=None, help="Optional fallback model after retry attempts fail.")
    parser.add_argument(
        "--thinking-enabled",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_THINKING_ENABLED,
        help="Request provider thinking/reasoning mode when the target API supports it.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=os.getenv("CTR_EVAL_REASONING_EFFORT", "medium"),
        help="Reasoning effort used by compatible OpenAI-style reasoning models.",
    )
    parser.add_argument("--max-seconds", type=float, default=30.0, help="Simulator max seconds per solution.")
    parser.add_argument(
        "--validator-backend",
        choices=("browser", "headless"),
        default=os.getenv("CTR_EVAL_VALIDATOR_BACKEND", "browser"),
        help="Simulator backend used to validate commands. Defaults to browser.",
    )
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--show-reference", action="store_true")
    parser.add_argument(
        "--video-source",
        choices=("mp4",),
        default="mp4",
        help="Video file variant to send or sample. Only mp4 is available.",
    )
    parser.add_argument(
        "--video-part-type",
        choices=("video_url", "input_video", "image_frames"),
        default="video_url",
        help="Message content part used for the video payload.",
    )
    parser.add_argument(
        "--video-detail",
        choices=("low", "high", "auto"),
        default=None,
        help="Optional video detail hint for providers that support it.",
    )
    parser.add_argument(
        "--video-max-frames",
        type=int,
        default=None,
        help="Optional maximum number of sampled video frames for providers that support it.",
    )
    parser.add_argument(
        "--video-fps",
        type=float,
        default=None,
        help="Optional video sampling fps for providers that support it.",
    )
    parser.add_argument(
        "--video-frame-width",
        type=int,
        default=960,
        help="Image width used when --video-part-type image_frames samples local video frames.",
    )
    parser.add_argument(
        "--video-frame-quality",
        type=float,
        default=0.85,
        help="JPEG quality used when --video-part-type image_frames samples local video frames.",
    )
    return parser


def select_item_paths(args: argparse.Namespace) -> list[Path]:
    if args.level_list_json is not None:
        _, targets = load_eval_targets_json(args.level_list_json)
        paths = [load_eval_item(target, data_dir=args.data_dir)[0] for target in targets]
    elif args.all:
        paths = list_eval_item_paths(args.data_dir)
    else:
        paths = [load_eval_item(args.level, data_dir=args.data_dir)[0]]

    if args.limit is not None:
        paths = paths[: args.limit]
    return paths


def print_model_output_debug(level_id: str, provider_label: str, raw_model_output: str, parsed_commands: str) -> None:
    print(f"=== Model Output Debug | {provider_label} | {level_id} ===")
    print("Raw model output:")
    print(raw_model_output.strip() or "(empty output)")
    if parsed_commands and parsed_commands.strip() != raw_model_output.strip():
        print("Parsed commands:")
        print(parsed_commands)
    print()


def print_batch_summary(
    results: list[dict[str, Any]],
    total_requested: int,
    skipped: dict[str, int] | None = None,
) -> None:
    skipped = skipped or {}
    won = sum(1 for item in results if item.get("evaluation", {}).get("won"))
    invalid = sum(1 for item in results if item.get("evaluation", {}).get("evaluation_status") == "invalid_output")
    saved = len(results)
    print("=== Batch Summary ===")
    print(
        json.dumps(
            {
                "total_requested_items": total_requested,
                "saved_result_items": saved,
                "skipped_existing_items": skipped.get("existing", 0),
                "skipped_request_error_items": skipped.get("request_error", 0),
                "skipped_invalid_output_items": skipped.get("invalid_output", 0),
                "skipped_simulator_error_items": skipped.get("simulator_error", 0),
                "skipped_runtime_error_items": skipped.get("runtime_error", 0),
                "won_items": won,
                "invalid_output_items": invalid,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print()


def build_result_payload(
    item_path: Path,
    eval_item: dict[str, Any],
    completion: dict[str, Any],
    parsed_json: dict[str, Any] | None,
    commands: str,
    parse_errors: list[str],
    evaluation: dict[str, Any],
    args: argparse.Namespace,
    provider: str,
    timing: dict[str, float],
) -> dict[str, Any]:
    return {
        "level_id": eval_item.get("level_id", item_path.stem),
        "data_item_path": str(item_path),
        "level_file": eval_item.get("level_file"),
        "video": eval_item.get("video"),
        "model_output": {
            "raw": completion.get("raw_content_text", ""),
            "parsed_json": parsed_json,
            "commands": commands,
            "parse_errors": parse_errors,
            "reasoning_content": completion.get("reasoning_content", ""),
        },
        "reference_solution": eval_item.get("reference_solution"),
        "evaluation": evaluation,
        "model": {
            "provider": provider,
            "model_name": args.model,
            "base_url": args.base_url,
            "timeout_seconds": args.timeout_seconds,
            "max_tokens": args.max_tokens,
            "max_retries": args.max_retries,
            "fallback_model": getattr(args, "fallback_model", None),
            "thinking_enabled": getattr(args, "thinking_enabled", True),
        },
        "completion": {
            "used_model_name": completion.get("response_model"),
            "response_id": completion.get("response_id"),
            "finish_reason": completion.get("finish_reason"),
            "usage": completion.get("usage"),
            "attempt_count": completion.get("attempt_count"),
            "attempts": completion.get("attempts"),
            "suspected_truncated_output": completion.get("suspected_truncated_output"),
            "retried_for_truncation": completion.get("retried_for_truncation"),
            "truncation_retry_count": completion.get("truncation_retry_count"),
            "request_duration_seconds": completion.get("request_duration_seconds"),
            "reasoning_char_count": completion.get("reasoning_char_count"),
            "thinking_request_mode": completion.get("thinking_request_mode"),
            "rate_limit_wait_seconds": completion.get("rate_limit_wait_seconds"),
            "request_error": completion.get("request_error"),
        },
        "timing": timing,
        "saved_at_utc": utc_timestamp(),
    }


RequestCompletion = Callable[[Any, Path, dict[str, Any], argparse.Namespace, str | None], dict[str, Any]]


def run_eval_loop(
    args: argparse.Namespace,
    client: Any,
    close_client: Callable[[], None] | None,
    provider: str,
    request_completion: RequestCompletion,
) -> int:
    from validator import evaluate_with_simulator

    item_paths = select_item_paths(args)
    args.results_dir = resolve_results_dir(args)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== Request Config | {provider} ===")
    print(f"model       : {args.model}")
    print(f"base_url    : {args.base_url or '<provider default>'}")
    print(f"data_dir    : {args.data_dir}")
    print(f"results_dir : {args.results_dir}")
    print(f"items       : {len(item_paths)}")
    print(f"max_tokens  : {args.max_tokens}")
    print(f"max_retries : {args.max_retries}")
    print(f"fallback    : {getattr(args, 'fallback_model', None) or '<none>'}")
    print(f"thinking    : {'enabled' if getattr(args, 'thinking_enabled', True) else 'disabled'}")
    print(f"validator   : {args.validator_backend}")
    print(f"skip_existing: {args.skip_existing}")
    print()

    results: list[dict[str, Any]] = []
    skipped = {
        "existing": 0,
        "request_error": 0,
        "invalid_output": 0,
        "simulator_error": 0,
        "runtime_error": 0,
    }
    try:
        for item_path in item_paths:
            result_path = args.results_dir / f"{item_path.stem}.json"
            if args.skip_existing and result_path.exists():
                print(f"Skip existing result: {result_path}")
                skipped["existing"] += 1
                continue

            _, eval_item = load_eval_item(item_path)
            level_id = str(eval_item.get("level_id", item_path.stem))
            print(f"=== Evaluating {level_id} ===")

            last_completion: dict[str, Any] | None = None
            request_errors: list[str] = []
            attempt_records: list[dict[str, Any]] = []
            total_request_duration_seconds = 0.0
            attempt_model_names = build_attempt_model_names(args)
            for attempt_index, attempt_model_name in enumerate(attempt_model_names, start=1):
                retry_note = None
                if attempt_index > 1:
                    retry_note = (
                        "Your previous response could not be parsed as the required JSON. "
                        "Return one complete JSON object with a non-empty commands string."
                    )
                attempt_args = clone_args_with_model(args, attempt_model_name)
                try:
                    completion = request_completion(client, item_path, eval_item, attempt_args, retry_note)
                except Exception as exc:  # noqa: BLE001
                    message = f"{type(exc).__name__}: {exc}"
                    request_errors.append(message)
                    completion = {
                        "raw_content_text": "",
                        "finish_reason": "request_error",
                        "response_model": attempt_model_name,
                        "request_duration_seconds": 0.0,
                        "request_error": message,
                    }
                    last_completion = completion
                    print(f"Attempt {attempt_index}: request_error={message}")
                    break
                request_duration = float(completion.get("request_duration_seconds", 0.0) or 0.0)
                total_request_duration_seconds += request_duration
                completion["suspected_truncated_output"] = is_retryable_completion(completion)
                attempt_record = {
                    "attempt_index": attempt_index,
                    "model_name": attempt_model_name,
                    "is_fallback_model": bool(getattr(args, "fallback_model", None))
                    and attempt_model_name == getattr(args, "fallback_model", None),
                    "finish_reason": completion.get("finish_reason"),
                    "response_id": completion.get("response_id"),
                    "response_model": completion.get("response_model"),
                    "usage": completion.get("usage"),
                    "output_char_count": len(str(completion.get("raw_content_text", ""))),
                    "suspected_truncated_output": completion["suspected_truncated_output"],
                    "request_duration_seconds": round(request_duration, 6),
                    "thinking_request_mode": completion.get("thinking_request_mode"),
                }
                attempt_records.append(attempt_record)
                completion["attempts"] = list(attempt_records)
                completion["attempt_count"] = attempt_index
                completion["request_duration_seconds"] = round(total_request_duration_seconds, 6)
                completion["retried_for_truncation"] = len(attempt_records) > 1
                completion["truncation_retry_count"] = max(0, len(attempt_records) - 1)
                last_completion = completion
                print(
                    f"Attempt {attempt_index}: finish_reason={completion.get('finish_reason')} "
                    f"suspected_truncated={completion.get('suspected_truncated_output')} "
                    f"thinking={completion.get('thinking_request_mode') or 'unknown'}"
                )
                if not completion["suspected_truncated_output"]:
                    break

            completion = last_completion or {"raw_content_text": ""}
            raw_output = str(completion.get("raw_content_text", ""))
            parsed_json, json_errors = parse_model_json(raw_output)
            commands, command_errors = normalize_commands_from_model_json(parsed_json)
            parse_errors = [*json_errors, *command_errors]
            print_model_output_debug(level_id, provider, raw_output, commands)

            if request_errors:
                skipped["request_error"] += 1
                print(f"[Skip][RequestError] {level_id}: {'; '.join(request_errors)}")
                print("No result file will be written for this level.\n")
                continue

            if parse_errors:
                print(f"[InvalidOutput] {level_id}: model output failed JSON/command validation.")
                for reason in parse_errors:
                    print(f"  - {reason}")
                evaluation = {
                    "evaluation_status": "invalid_output",
                    "won": False,
                    "failure_reason": "; ".join(parse_errors),
                    "validation_errors": parse_errors,
                }
                timing = {
                    "model_response_seconds": float(completion.get("request_duration_seconds", 0.0) or 0.0),
                    "simulator_seconds": 0.0,
                }
            else:
                try:
                    evaluation = evaluate_with_simulator(
                        eval_item,
                        commands,
                        max_seconds=args.max_seconds,
                        backend=args.validator_backend,
                    )
                    timing = {
                        "model_response_seconds": float(completion.get("request_duration_seconds", 0.0) or 0.0),
                        "simulator_seconds": float(evaluation.pop("_wall_seconds", 0.0) or 0.0),
                    }
                except Exception as exc:  # noqa: BLE001
                    skipped["runtime_error"] += 1
                    print(f"[Skip][RuntimeError] {level_id}: {type(exc).__name__}: {exc}")
                    print("No result file will be written for this level.\n")
                    continue

                if evaluation.get("evaluation_status") == "invalid_output":
                    reasons = evaluation.get("validation_errors") or [
                        evaluation.get("failure_reason") or "invalid_output"
                    ]
                    print(f"[InvalidOutput] {level_id}: simulator rejected the command syntax.")
                    for reason in reasons:
                        print(f"  - {reason}")
                elif evaluation.get("evaluation_status") == "simulator_error":
                    reasons = evaluation.get("validation_errors") or [
                        evaluation.get("failure_reason") or "simulator_error"
                    ]
                    print(f"[SimulatorError] {level_id}: simulator crashed while executing parsed commands.")
                    for reason in reasons:
                        print(f"  - {reason}")


            result_payload = build_result_payload(
                item_path=item_path,
                eval_item=eval_item,
                completion=completion,
                parsed_json=parsed_json,
                commands=commands,
                parse_errors=parse_errors,
                evaluation=evaluation,
                args=args,
                provider=provider,
                timing=timing,
            )
            save_path = save_result_json(item_path, result_payload, args.results_dir)
            print(f"Result saved: {save_path}")
            print(json.dumps({"level_id": level_id, "evaluation": evaluation}, ensure_ascii=False, indent=2))
            print()

            if args.show_reference and not args.all:
                print("=== Reference Solution ===")
                print(str(eval_item.get("reference_solution") or "").strip())
                print()
            results.append(result_payload)
    finally:
        if close_client is not None:
            close_client()

    if args.all:
        print_batch_summary(results, len(item_paths), skipped)
    return 0 if results or skipped["existing"] else 1
