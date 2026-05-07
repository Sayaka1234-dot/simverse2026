# Cube1 Eval (SimVerse v1)

Evaluation pipeline for the **cube reconstruction** task: reconstruct the patternId and rotation of every outer face of a cube from a blank cross net + a top-down path-imprint image.

## Dataset

Tasks: [`cube1/data/task_jsons/*.json`](../data/task_jsons/) (502 levels). The gold answer follows [docs/PROMPT_SKELETON.md §3.2](../../docs/PROMPT_SKELETON.md):

```json
{
  "answer": {
    "faces": {
      "TOP":    {"patternId": "smile",    "rotation":  90},
      "BOTTOM": {"patternId": "triangle", "rotation":  90},
      "FRONT":  {"patternId": "G",        "rotation":  90},
      "BACK":   {"patternId": "5",        "rotation":   0},
      "LEFT":   {"patternId": "4",        "rotation": 270},
      "RIGHT":  {"patternId": "smile",    "rotation": 180}
    }
  }
}
```

The legacy bare face map was migrated by [`migrate_dataset.py`](migrate_dataset.py); the original is preserved in `legacy_answer` for one release.

## Module layout

| File | Role |
|---|---|
| [`prompts.py`](prompts.py) | 5-section system + 9-section user prompt + multimodal messages (`build_messages`). |
| [`parsers.py`](parsers.py) | `extract_final_json` and `parse_cube1_answer`: pulls `FINAL_JSON: {...}` and validates the faces schema (allowed patternIds, valid rotations, "?" sentinel rule). |
| [`validator.py`](validator.py) | `validate(parsed_answer, gold_answer, task) -> Verdict` — partial credit by face. |
| [`engine_interface.py`](engine_interface.py) | Per-face equality + summary metrics. |
| [`eval_common.py`](eval_common.py) | Internal helpers (PuzzleTask, FaceAnswer, request_model_answer, transient retries). The legacy `build_*_prompt_for_eval` names are now thin shims around `prompts.py`. |
| `eval_local.py`, `eval_<provider>_local.py` | Provider-specific runners. They keep importing the legacy names but transparently use the new prompts. |

## Model output contract

```
FINAL_JSON: {"faces":{"TOP":{"patternId":"...","rotation":0}, ..., "RIGHT":{...}}}
```

Six required face keys. patternId from the per-task allowed list, or the literal `"?"` for "cannot be uniquely determined". rotation in `{0,90,180,270}`. When `patternId == "?"`, rotation is forced to 0.

## Running

```bash
export OPENAI_API_KEY=...

# One sample
python eval_local.py ../data/task_jsons/C001.json

# Whole directory
python eval_local.py ../data/task_jsons --skip-existing

# Manifest
python eval_local.py ../data/manifests/reconstruct_tasks.jsonl --skip-existing
```

## Migrating

```bash
python migrate_dataset.py            # in place
python migrate_dataset.py --dry-run  # report only
```
