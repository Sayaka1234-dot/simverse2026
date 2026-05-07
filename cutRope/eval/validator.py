from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eval_common import DEFAULT_DATA_DIR, EVAL_ROOT, PROJECT_ROOT, load_eval_item


@dataclass
class Verdict:
    """SimVerse v1 verdict shape per docs/EVAL_CONTRACT.md §4."""

    status: str                    # "passed" | "failed" | "invalid_output"
    score: float                   # 0.0 .. 1.0  (1.0 only on a 3-star win; 2/3 and 1/3 = partial credit)
    errors: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def _level_file_name(eval_item: dict[str, Any]) -> str:
    level_file = eval_item.get("level_file")
    if not isinstance(level_file, str) or not level_file:
        raise ValueError("eval item is missing level_file")
    return Path(level_file).name


def classify_browser_result_error(error: str) -> str:
    normalized = str(error or "").strip()
    if not normalized:
        return "failed"

    command_error_patterns = (
        r"\bLine\s+\d+\s*:",
        r"\bCommand parse error\b",
        r"\bUnknown command\b",
        r"\bInvalid \w+(?:_\w+)* syntax\b",
        r"\bInvalid \w+(?:_\w+)* index\b",
        r"\bmust be a positive\b",
        r"\bcannot use both\b",
    )
    if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in command_error_patterns):
        return "invalid_output"

    return "simulator_error"


def evaluate_with_simulator(
    eval_item: dict[str, Any],
    commands: str,
    max_seconds: float = 30.0,
    backend: str = "browser",
) -> dict[str, Any]:
    started_at = time.perf_counter()
    if backend not in {"browser", "headless"}:
        raise ValueError(f"Unknown validator backend: {backend}")

    if not commands.strip():
        return {
            "evaluation_status": "invalid_output",
            "won": False,
            "failure_reason": "Empty command script.",
            "validation_errors": ["Empty command script."],
            "validator_backend": backend,
            "_wall_seconds": round(time.perf_counter() - started_at, 6),
        }

    case = {
        "cases": [
            {
                "level": _level_file_name(eval_item),
                "commands": commands,
                "maxSeconds": max_seconds,
            }
        ]
    }

    tmp_root = EVAL_ROOT / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = tmp_root / f"ctr_eval_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=False)
    try:
        input_path = tmp_dir / "case.json"
        output_path = tmp_dir / "result.json"
        input_path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")

        npm_script = "eval:browser-batch" if backend == "browser" else "eval:batch"

        completed = subprocess.run(
            [
                "cmd",
                "/c",
                "npm",
                "run",
                npm_script,
                "--",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        if completed.returncode != 0:
            return {
                "evaluation_status": "simulator_error",
                "won": False,
                "failure_reason": f"Simulator command failed with exit code {completed.returncode}.",
                "validation_errors": [completed.stderr.strip() or completed.stdout.strip()],
                "validator_backend": backend,
                "subprocess": {
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                "_wall_seconds": round(time.perf_counter() - started_at, 6),
            }

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or not results:
            return {
                "evaluation_status": "simulator_error",
                "won": False,
                "failure_reason": "Simulator did not return a result row.",
                "validation_errors": [f"Missing results[0] from {npm_script} output."],
                "validator_backend": backend,
                "raw_output": payload,
                "_wall_seconds": round(time.perf_counter() - started_at, 6),
            }

        result = results[0]
        if not isinstance(result, dict):
            return {
                "evaluation_status": "simulator_error",
                "won": False,
                "failure_reason": "Simulator returned a non-object result row.",
                "validation_errors": [str(result)],
                "validator_backend": backend,
                "_wall_seconds": round(time.perf_counter() - started_at, 6),
            }

        error = str(result.get("error") or "").strip()
        won = bool(result.get("won"))
        status = "won" if won else "failed"
        failure_reason = ""
        validation_errors: list[str] = []

        if error:
            status = classify_browser_result_error(error)
            failure_reason = error
            validation_errors.append(error)
        elif not won:
            reason = str(result.get("reason") or "unknown")
            status = "failed"
            failure_reason = f"Simulator result was {reason}; candy did not reach win state."

        return {
            "evaluation_status": status,
            "won": won,
            "stars": result.get("stars", 0),
            "score": result.get("score", 0),
            "time": result.get("time", 0),
            "frames": result.get("frames", 0),
            "reason": result.get("reason"),
            "failure_reason": failure_reason,
            "validation_errors": validation_errors,
            "simulator_result": result,
            "validator_backend": backend,
            "_wall_seconds": round(time.perf_counter() - started_at, 6),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def validate(
    *,
    parsed_answer: dict[str, Any],
    gold_answer: dict[str, Any],
    task: dict[str, Any],
    project_root: Path | None = None,
    max_seconds: float = 30.0,
    backend: str = "browser",
) -> Verdict:
    """SimVerse v1 entry per docs/EVAL_CONTRACT.md §4.

    `parsed_answer` and `gold_answer` are both
    `{"commands": "...", "reason": "...", "confidence": float}` per
    docs/PROMPT_SKELETON.md §3.4. The simulator is the source of truth for
    "did the script win"; gold_answer is one known-valid script kept for
    solver-coverage statistics, not for equality checks.
    """
    commands = parsed_answer.get("commands") if isinstance(parsed_answer, dict) else None
    if not isinstance(commands, str) or not commands.strip():
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["commands_missing_or_empty"],
            detail={},
        )
    if "wait_frames" in commands:
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["wait_frames_not_allowed"],
            detail={},
        )

    sim = evaluate_with_simulator(task, commands, max_seconds=max_seconds, backend=backend)

    status = str(sim.get("evaluation_status", "")).lower()
    won = bool(sim.get("won"))
    stars = int(sim.get("stars") or 0)

    if status == "invalid_output":
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=list(sim.get("validation_errors") or ["engine_invalid_output"]),
            detail={"engine_result": sim, "gold_answer": gold_answer},
        )
    if status == "simulator_error":
        return Verdict(
            status="invalid_output",
            score=0.0,
            errors=["simulator_error"] + list(sim.get("validation_errors") or []),
            detail={"engine_result": sim, "gold_answer": gold_answer},
        )

    if won:
        # 3 stars = full credit; partial stars = partial credit.
        score = round(min(1.0, max(stars, 1) / 3.0), 6)
        return Verdict(
            status="passed",
            score=score,
            errors=[] if stars == 3 else [f"stars_only_{stars}_of_3"],
            detail={"engine_result": sim, "gold_answer": gold_answer},
        )

    return Verdict(
        status="failed",
        score=0.0,
        errors=["candy_did_not_reach_target"],
        detail={"engine_result": sim, "gold_answer": gold_answer},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a command script with the Cut the Rope simulator.")
    parser.add_argument("--level", default="rope-000", help="Eval data item id or JSON path.")
    parser.add_argument("--commands", default=None, help="Command script to evaluate.")
    parser.add_argument(
        "--commands-from-reference",
        action="store_true",
        help="Use reference_solution from the eval item.",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument(
        "--backend",
        choices=["browser", "headless"],
        default="browser",
        help="Simulator backend. browser uses Playwright and real browser-loaded assets; headless uses the old Node shim.",
    )
    args = parser.parse_args()

    _, item = load_eval_item(args.level, data_dir=args.data_dir)
    commands = args.commands
    if args.commands_from_reference:
        commands = str(item.get("reference_solution") or "")
    if commands is None:
        raise SystemExit("Pass --commands or --commands-from-reference.")

    result = evaluate_with_simulator(item, commands, max_seconds=args.max_seconds, backend=args.backend)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("won") else 1


if __name__ == "__main__":
    raise SystemExit(main())
