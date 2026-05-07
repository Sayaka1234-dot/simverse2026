from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))


DEFAULT_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "claude-opus-4-6")
DEFAULT_LEVELS_DIR = PROJECT_ROOT / "levels"
DEFAULT_RESULTS_ROOT = EVAL_ROOT / "results"
DEFAULT_RESULTS_DIR = DEFAULT_RESULTS_ROOT / DEFAULT_MODEL_NAME
DEFAULT_JSON_PATH = DEFAULT_LEVELS_DIR / "level001.json"
DEFAULT_LEVEL_ID = "level001"
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")

DEFAULT_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "900"))
DEFAULT_TRUST_ENV = os.getenv("OPENAI_TRUST_ENV", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
} 


def build_client(
    base_url: str = DEFAULT_BASE_URL,
    api_key: str = DEFAULT_API_KEY,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    trust_env: bool = DEFAULT_TRUST_ENV,
):
    from openai import OpenAI

    timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds, read=timeout_seconds)
    http_client = httpx.Client(timeout=timeout, trust_env=trust_env)
    client = OpenAI(base_url=base_url, api_key=api_key, http_client=http_client)
    return client, http_client


def encode_image(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def image_to_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{encode_image(image_path)}"


def load_level_json(
    target_json: str | Path,
    levels_dir: Path = DEFAULT_LEVELS_DIR,
) -> tuple[Path, dict[str, Any]]:
    if isinstance(target_json, Path):
        candidate = target_json
    else:
        text = str(target_json).strip()
        if text.endswith(".json") or any(sep in text for sep in ("/", "\\")):
            candidate = Path(text)
        else:
            candidate = levels_dir / f"{text}.json"

    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()

    if not candidate.exists():
        raise FileNotFoundError(f"关卡 JSON 不存在: {candidate}")

    payload = json.loads(candidate.read_text(encoding="utf-8"))
    return candidate, payload


def list_level_json_paths(levels_dir: Path = DEFAULT_LEVELS_DIR) -> list[Path]:
    return sorted(levels_dir.glob("level*.json"))


def load_level_targets_json(level_list_json: str | Path) -> tuple[Path, list[str]]:
    level_list_path = Path(level_list_json)
    if not level_list_path.is_absolute():
        project_candidate = (PROJECT_ROOT / level_list_path).resolve()
        eval_candidate = (EVAL_ROOT / level_list_path).resolve()
        if project_candidate.exists():
            level_list_path = project_candidate
        else:
            level_list_path = eval_candidate

    if not level_list_path.exists():
        raise FileNotFoundError(f"关卡列表 JSON 不存在: {level_list_path}")

    payload = json.loads(level_list_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw_levels = payload
    elif isinstance(payload, dict):
        raw_levels = payload.get("levels")
    else:
        raise ValueError("关卡列表 JSON 必须是数组，或包含 levels 数组字段的对象。")

    if not isinstance(raw_levels, list) or not raw_levels:
        raise ValueError("关卡列表 JSON 中的 levels 必须是非空数组。")

    level_targets = [str(item).strip() for item in raw_levels if str(item).strip()]
    if not level_targets:
        raise ValueError("关卡列表 JSON 中没有可用的关卡条目。")

    return level_list_path, level_targets


def resolve_level_asset_path(level_path: Path, relative_path: str) -> Path:
    asset_path = (level_path.parent / relative_path).resolve()
    if not asset_path.exists():
        raise FileNotFoundError(f"图片资源不存在: {asset_path}")
    return asset_path


def resolve_level_image_path(level_data: dict[str, Any]) -> Path:
    image_assets = level_data.get("imageAssets", {})
    target_path = image_assets.get("target")
    if not target_path:
        raise ValueError("关卡 JSON 缺少 imageAssets.target")
    level_name = level_data.get("name", "unknown")
    level_number = level_name.split()[-1] if " " in level_name else level_name
    level_json_path = DEFAULT_LEVELS_DIR / f"level{level_number}.json"
    return resolve_level_asset_path(level_json_path, target_path)


def build_system_message() -> str:
    """SimVerse v1: delegates to prompts.build_system_prompt for a single source of truth."""
    from prompts import build_system_prompt
    return build_system_prompt()


def build_prompt(level_data: dict[str, Any]) -> str:
    """SimVerse v1: delegates to prompts.build_user_prompt."""
    from prompts import build_user_prompt
    return build_user_prompt(level_data)


def build_multimodal_content(level_path: Path, level_data: dict[str, Any]) -> list[dict[str, Any]]:
    """SimVerse v1: delegates to prompts.build_messages but returns just the user's
    content array (legacy callers wrap their own role envelope around it)."""
    from prompts import build_messages
    messages = build_messages(level_path, level_data)
    user_msg = next((m for m in messages if m.get("role") == "user"), None)
    if user_msg is None or not isinstance(user_msg.get("content"), list):
        return []
    return list(user_msg["content"])


def extract_text_content(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content.strip()

    if isinstance(message_content, list):
        text_chunks: list[str] = []
        for item in message_content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_chunks.append(item.get("text", ""))
                elif "text" in item:
                    text_chunks.append(str(item["text"]))
            else:
                text_value = getattr(item, "text", None)
                if text_value:
                    text_chunks.append(str(text_value))
        return "\n".join(chunk.strip() for chunk in text_chunks if chunk.strip()).strip()

    return str(message_content).strip()


def flatten_rich_text(value: Any) -> str:
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
                parts.append(flatten_rich_text(item))
        return "".join(parts)
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
        candidates.extend([message.get("reasoning_content"), message.get("reasoning")])
    else:
        candidates.extend(
            [
                getattr(message, "reasoning_content", None),
                getattr(message, "reasoning", None),
            ]
        )

    reasoning_chunks = [flatten_rich_text(candidate).strip() for candidate in candidates]
    reasoning_chunks = [chunk for chunk in reasoning_chunks if chunk]
    return "\n".join(reasoning_chunks).strip()


def save_result_json(level_path: Path, payload: dict[str, Any], results_dir: Path = DEFAULT_RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / f"{level_path.stem}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def get_invalid_output_reasons(engine_result: dict[str, Any]) -> list[str]:
    if engine_result.get("evaluation_status") != "invalid_output":
        return []

    raw_errors = engine_result.get("validation_errors") or []
    reasons = [str(item).strip() for item in raw_errors if str(item).strip()]
    return reasons or ["Engine returned invalid_output, but no validation_errors were provided."]


def print_invalid_output_result(
    level_id: str,
    engine_result: dict[str, Any],
    model_output: str | None = None,
    raw_model_output: str | None = None,
) -> None:
    reasons = get_invalid_output_reasons(engine_result)
    if not reasons:
        return

    normalized_output = (model_output or "").strip()
    raw_output = (raw_model_output or "").strip()
    preferred_output = raw_output or normalized_output

    print(f"[InvalidOutput] {level_id}: model output could not be validated.")
    print("Model output:")
    if preferred_output:
        print(preferred_output)
    else:
        print("(empty output)")

    if raw_output and normalized_output and raw_output != normalized_output:
        print("Normalized operation lines:")
        print(normalized_output if normalized_output else "(empty output)")

    print("Reasons:")
    for index, reason in enumerate(reasons, start=1):
        print(f"  {index}. {reason}")



def print_model_output_debug(
    level_id: str,
    provider_label: str,
    model_output: str | None = None,
    raw_model_output: str | None = None,
    reasoning_content: str | None = None,
) -> None:
    normalized_output = (model_output or "").strip()
    raw_output = (raw_model_output or "").strip()
    reasoning_output = (reasoning_content or "").strip()

    print(f"=== Model Output Debug | {provider_label} | {level_id} ===")
    print("Raw model output:")
    print(raw_output if raw_output else "(empty output)")

    if normalized_output and normalized_output != raw_output:
        print("Normalized operation lines:")
        print(normalized_output)

    if reasoning_output:
        print("Reasoning content:")
        print(reasoning_output)

    print()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
