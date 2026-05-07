from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from eval_common.schemas import LampTask


def load_task_json(task_json_path: str | Path) -> tuple[Path, LampTask]:
    path = Path(task_json_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Task JSON does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return path, LampTask.from_dict(payload)


def iter_manifest_rows(manifest_path: str | Path) -> Iterable[dict[str, Any]]:
    path = Path(manifest_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Task manifest does not exist: {path}")

    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def iter_task_json_files(target_dir: str | Path) -> list[Path]:
    directory = Path(target_dir).resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Task directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Task target is not a directory: {directory}")

    return sorted(path for path in directory.rglob("*.json") if path.name != "manifest.jsonl")


def load_json_payload(json_path: str | Path) -> tuple[Path, Any]:
    path = Path(json_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"JSON file does not exist: {path}")

    return path, json.loads(path.read_text(encoding="utf-8-sig"))


def is_task_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and "public" in payload and "validator" in payload


def iter_selection_rows(selection_path: str | Path) -> Iterable[dict[str, Any]]:
    path, payload = load_json_payload(selection_path)

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("samples"), list):
        rows = payload["samples"]
    else:
        raise ValueError(f"Selection JSON must be a list or an object with a 'samples' array: {path}")

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"Selection row must be a JSON object: {path}")
        yield row


def resolve_task_path(project_root: str | Path, row: dict[str, Any]) -> Path:
    task_path = row.get("task_path")
    if not isinstance(task_path, str) or not task_path.strip():
        raise ValueError(f"Selection row is missing a non-empty task_path: {row}")

    resolved = (Path(project_root).resolve() / task_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Referenced task JSON does not exist: {resolved}")
    return resolved


def resolve_task_target_paths(task_target: str | Path, *, project_root: str | Path) -> list[Path]:
    target = Path(task_target).resolve()

    if target.is_dir():
        return iter_task_json_files(target)

    if not target.exists():
        raise FileNotFoundError(f"Task target does not exist: {target}")

    if target.suffix.lower() == ".jsonl":
        return [resolve_task_path(project_root, row) for row in iter_manifest_rows(target)]

    if target.suffix.lower() != ".json":
        return [target]

    _, payload = load_json_payload(target)
    if is_task_payload(payload):
        return [target]

    return [resolve_task_path(project_root, row) for row in iter_selection_rows(target)]
