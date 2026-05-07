"""Backward-compat shim. The canonical prompt builder now lives at
`lamp/eval-thinking/prompts.py` per docs/EVAL_CONTRACT.md §7.

This module is kept so the legacy provider variants (eval_qwen_local.py,
eval_glm_local.py, ...) keep importing without code churn. New code should
import from `prompts` directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# `prompts.py` lives at the eval-thinking root, which is on sys.path when
# any of the runners executes. Importing it directly keeps a single source
# of truth for prompt content.
from prompts import build_messages, build_system_prompt, build_user_prompt


def build_multimodal_messages(task: Any, *, project_root: Path) -> list[dict[str, Any]]:
    """Old name kept for backward compatibility."""
    return build_messages(task, project_root=project_root)


__all__ = [
    "build_multimodal_messages",
    "build_messages",
    "build_system_prompt",
    "build_user_prompt",
]
