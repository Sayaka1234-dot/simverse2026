# Lamp Eval (SimVerse v1)

Evaluation pipeline for the mechanical lamp targeting task.

## Dataset

Levels live in [`lamp/data/levels/lamp-*.json`](../data/levels/) — the same files served by the browser demo. Per-level images: [`lamp/data/images/<sample_id>.png`](../data/images/).

Each level JSON carries the gold answer in the field `answer` per [docs/PROMPT_SKELETON.md §3.5](../../docs/PROMPT_SKELETON.md):

```json
{
  "answer": {
    "actions": [
      {"joint": 1, "angle": -60},
      {"joint": 2, "angle": -135},
      ...
    ]
  }
}
```

The legacy flat-array form (`arm.answer: [-60, -135, ...]`) was migrated to this schema by [`migrate_dataset.py`](migrate_dataset.py); the original values are preserved under `legacy_answer` for one release.

## Module layout

| File | Role |
|---|---|
| [`prompts.py`](prompts.py) | Builds 5-section system + 9-section user prompt + multimodal messages (`build_messages`). |
| [`parsers.py`](parsers.py) | `extract_final_json` and `parse_lamp_answer`: pulls the `FINAL_JSON: {...}` line and validates the actions schema. |
| [`validator.py`](validator.py) | `validate(parsed_answer, gold_answer, task, project_root) -> Verdict` runs the geometry engine. |
| [`engine_interface.py`](engine_interface.py) | Pure-Python forward kinematics + obstacle collision check. |
| [`eval_common/`](eval_common/) | Internal helpers (dataset I/O, payload builders, network errors). Contains backward-compat shims so the legacy provider variants keep importing without code churn. |
| [`eval_local.py`](eval_local.py), `eval_<provider>_local.py` | Provider-specific runners; consume the modules above. To be merged into one `run_eval.py` in the eval-CLI unification step. |

## Model output contract

Final line of every reply must be:

```
FINAL_JSON: {"actions":[{"joint":1,"angle":<int>}, ...]}
```

See [`prompts.py:build_user_prompt`](prompts.py) for the full schema (one action per joint, joint 1-indexed, angle within `[angle_min, angle_max]` and a multiple of `angle_step`).

## Running

```bash
# 1. Set env keys (see top-level .env.example)
export OPENAI_API_KEY=...          # or DASHSCOPE_API_KEY for Qwen, etc.

# 2. Run one level
python eval_local.py ../data/levels/lamp-000.json

# 3. Run all
python eval_local.py ../data/levels --skip-existing

# 4. Run a subset
python eval_local.py random_50_tasks2.json --skip-existing
```

Provider variants (`eval_qwen_local.py`, `eval_glm_local.py`, ...) take the same arguments; see each file's header for the exact env vars and defaults.

## Migrating

To re-run the legacy → v1 dataset migration (idempotent):

```bash
python migrate_dataset.py
python migrate_dataset.py --dry-run   # report only, no writes
```
