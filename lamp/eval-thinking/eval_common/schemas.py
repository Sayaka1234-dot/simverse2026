"""Lamp task dataclasses. Reads `data/levels/lamp-*.json` directly (the canonical
SimVerse v1 format used by both the frontend demo and the eval pipeline)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LampTask:
    """One lamp puzzle level. Loaded directly from data/levels/lamp-*.json."""

    sample_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LampTask":
        sample_id = str(payload.get("id") or payload.get("sample_id") or "")
        if not sample_id:
            raise ValueError("Lamp task JSON is missing top-level 'id' or 'sample_id'.")
        return cls(sample_id=sample_id, payload=dict(payload))

    # ------- frontend / eval convenience accessors -------

    @property
    def difficulty(self) -> int:
        return int(self.payload.get("difficulty", 0))

    @property
    def workspace(self) -> dict[str, Any]:
        return dict(self.payload.get("workspace", {}))

    @property
    def origin(self) -> dict[str, float]:
        return dict(self.workspace.get("origin", {"x": 0, "y": 0}))

    @property
    def arm_base_offset(self) -> dict[str, float]:
        return dict(self.payload.get("armBaseOffset", {"x": 0, "y": 0}))

    @property
    def arm_base(self) -> dict[str, float]:
        offset = self.arm_base_offset
        return {"x": float(offset.get("x", 0)), "y": float(offset.get("y", 0))}

    @property
    def target(self) -> dict[str, float]:
        target = dict(self.payload.get("target", {"x": 0, "y": 0}))
        return {"x": float(target.get("x", 0)), "y": float(target.get("y", 0))}

    @property
    def light_radius(self) -> float:
        lamp = dict(self.payload.get("lamp", {}))
        return float(lamp.get("lightRadius", lamp.get("light_radius", 0)))

    @property
    def obstacles(self) -> list[dict[str, Any]]:
        return list(self.payload.get("obstacles", []))

    @property
    def arm(self) -> dict[str, Any]:
        return dict(self.payload.get("arm", {}))

    @property
    def segment_count(self) -> int:
        arm = self.arm
        explicit = arm.get("segmentCount")
        if isinstance(explicit, int):
            return explicit
        return len(arm.get("segments", []))

    @property
    def segments(self) -> list[int]:
        return [int(item.get("length", 0)) for item in self.arm.get("segments", [])]

    @property
    def angle_constraints(self) -> dict[str, int]:
        arm = self.arm
        return {
            "min": int(arm.get("angleMin", -180)),
            "max": int(arm.get("angleMax", 180)),
            "step": int(arm.get("angleStep", 5)),
        }

    @property
    def initial_angles(self) -> list[int]:
        return [int(angle) for angle in self.arm.get("initialAngles", [])]

    @property
    def gold_answer(self) -> dict[str, Any]:
        """The schema-locked `answer` field; see docs/PROMPT_SKELETON.md §3.5."""
        return dict(self.payload.get("answer", {}))

    @property
    def metadata(self) -> dict[str, Any]:
        meta = dict(self.payload.get("meta", {}))
        meta.setdefault("difficulty", self.difficulty)
        return meta

    @property
    def image_path(self) -> str:
        """Convention: data/images/<sample_id>.png next to data/levels/."""
        return f"data/images/{self.sample_id}.png"

    @property
    def validator(self) -> dict[str, Any]:
        """Legacy compat: pre-migration code expected `task.validator.target` and
        `task.validator.success_rule.radius`. Synthesize them from the new schema."""
        return {
            "target": self.target,
            "success_rule": {"radius": self.light_radius},
        }

    @property
    def public(self) -> dict[str, Any]:
        """Legacy compat: pre-migration eval scripts read `task.public.get(...)`.
        Expose the same fields drawn from the new SimVerse v1 dataset schema.
        New code should use the typed accessors (arm_base, obstacles, ...) instead."""
        return {
            "arm_base": self.arm_base,
            "target": self.target,
            "obstacles": self.obstacles,
            "segments": [{"length": length} for length in self.segments],
            "segment_count": self.segment_count,
            "angle_constraints": self.angle_constraints,
            "lamp": {"light_radius": self.light_radius},
            "image": self.image_path,
        }


@dataclass
class ParsedAnswer:
    """Parsed and structurally-validated FINAL_JSON payload from the model."""

    actions: list[dict[str, int]]
    angles: list[int]
    raw_text: str = ""


@dataclass
class ResultRecord:
    sample_id: str
    evaluation_status: str
    is_valid_format: bool
    is_valid_solution: bool
    raw_model_output: str
    normalized_answer: dict[str, Any] | None
    engine_result: dict[str, Any] | None
