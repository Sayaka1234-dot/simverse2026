# Cube2 Eval (SimVerse v1)

Evaluation pipeline for the **cube goal-roll (top face)** task: output a sequence of N/S/E/W rolls so that the cube's top face matches the target.

## Dataset

Tasks: [`cube2/data2/task_jsons/*.json`](../data2/task_jsons/) (502 levels). The gold answer follows [docs/PROMPT_SKELETON.md §3.3](../../docs/PROMPT_SKELETON.md):

```json
{ "answer": { "directions": ["N", "E", "S"] } }
```

Cube2 is **open-ended**: any direction sequence that produces the target top face is valid. `answer.directions` is one known-valid reference sequence; the validator confirms a model answer by simulating the engine, not by string equality.

The legacy face-map answer (which was specific to the cube reconstruction task, not goal-roll) was preserved under `legacy_answer` by [`migrate_dataset.py`](migrate_dataset.py).

## Module layout

| File | Role |
|---|---|
| [`prompts.py`](prompts.py) | 5-section system + 9-section user prompt + multimodal messages (`build_messages`). |
| [`parsers.py`](parsers.py) | `extract_final_json` and `parse_cube2_answer`: pulls `FINAL_JSON: {...}` and validates the directions schema. |
| [`validator.py`](validator.py) | `validate(parsed_answer, gold_answer, task) -> Verdict`. Runs the engine, marks "passed" iff the simulated top face matches the target. |
| [`engine_interface.py`](engine_interface.py) | Pure-Python cube state + roll simulation. |
| [`eval_common.py`](eval_common.py) | Internal helpers (GoalRollTask, ModelAnswer, request_model_answer, transient retries). The legacy `build_*_for_eval` names are now thin shims around `prompts.py`. |
| `eval_local.py`, `eval_<provider>_local.py` | Provider-specific runners. |

## Model output contract

```
FINAL_JSON: {"directions":["N","E","S"]}
```

Each token in `{"N","S","E","W"}`. Length 1..`DEFAULT_MAX_DIRECTION_STEPS` (= 20). Multiple sequences may be valid; output any one.

## Running

```bash
export OPENAI_API_KEY=...

python eval_local.py ../data2/task_jsons/C001.json
python eval_local.py ../data2/task_jsons --skip-existing
python eval_local.py --manifest ../data2/manifests/goal_roll_tasks.jsonl --skip-existing
```

## Migrating

```bash
python migrate_dataset.py            # in place
python migrate_dataset.py --dry-run  # report only
```
