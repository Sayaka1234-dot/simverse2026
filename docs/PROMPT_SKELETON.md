# Prompt Skeleton

**Languages: English (this file) | [中文](PROMPT_SKELETON_zh.md)**

The contract every task's prompt builder must follow. The five tasks each implement their own prompt builder file in their own `eval*/prompts.py` (or `prompts.py` next to their `run_eval.py`). The five files **share no code** — they only share this skeleton, enforced by code review.

## 1. System prompt (5 sections, fixed order)

```
[1] ROLE       — One sentence: "You are a <task type> solver. <one sentence task summary>."
[2] INPUT      — One paragraph: list every input modality (images / video / structured fields).
[3] REASONING  — Verbatim:
                 "You may reason step by step before the final answer.
                  Place your final answer on the very last line of your reply,
                  in the form: FINAL_JSON: <one-line JSON>"
[4] OUTPUT     — One paragraph: state the JSON object's required schema name and
                 hard rules: no Markdown code fences around FINAL_JSON, no extra text
                 after FINAL_JSON, exactly one FINAL_JSON line.
[5] FAILSAFE   — One paragraph: when information is insufficient, the model must
                 still emit a valid FINAL_JSON (using sentinel values like "?")
                 rather than refusing or returning prose.
```

Every section appears in every task's system prompt. Length ≈ 120–200 words total.

## 2. User prompt (9 sections, fixed order, fixed headers)

The headers are literal — copy them verbatim:

```
## 1. TASK
   One sentence: the goal.
   One sentence: the win condition.

## 2. WORLD MODEL
   Bullet list of every game-element term (candy, joint, face, shape, cube, ...).
   For each term, one sentence of definition.

## 3. VISUAL LEGEND
   Bullet list explaining every color, symbol, and overlay in the input image/video.
   Coordinate system convention: origin location, axis direction, units.

## 4. INPUT FIELDS
   Bullet list of all structured task parameters (level id, grid size, segment lengths,
   roll sequence, observed sequence, allowed angle range, ...).
   Format: "- key: value"

## 5. ACTION VOCABULARY
   Bullet list of every legal action atom or answer primitive.
   For each atom: name, parameters, optional condition clause.

## 6. CONSTRAINTS
   Bullet list of hard constraints a valid answer must satisfy
   (angle step, sequence length cap, uniqueness, no overlap, ...).

## 7. SOLVING ADVICE
   Optional bullet list of generic heuristics. Keep neutral; do not bias toward
   a specific answer for the current task instance.

## 8. OUTPUT SCHEMA
   Inline FINAL_JSON example with placeholder values, plus a per-field
   description of types and allowed values.

## 9. FINAL INSTRUCTION
   Verbatim two sentences:
   "You may include reasoning above, but the very last line of your reply must
    start with FINAL_JSON: followed by exactly one valid JSON object.
    Do not wrap FINAL_JSON in code fences and do not write anything after it."
```

Each section appears in every task's user prompt. If a task genuinely has nothing to put in a section (e.g. no obstacles → empty constraints sublist), the section header still appears with the line `(none for this task)`.

## 3. Per-task JSON schemas (locked)

Every task's `FINAL_JSON: <object>` matches the corresponding schema below. The dataset's gold `answer` field uses the **same schema** so that one JSON loader serves both model output and ground truth.

Each per-level dataset file ALSO carries a top-level `prompt` field with the literal text the model receives, so HuggingFace dataset users can reproduce evaluations without rebuilding prompts:

```json
{
  "prompt": {
    "system": "<5-section system prompt text — see §1>",
    "user":   "<9-section user prompt text — see §2>"
  },
  "answer": { /* per-task schema below */ },
  "...": "...task-specific fields"
}
```

Each task's `prompts.py` first reads `task.prompt.system` / `task.prompt.user` if present and falls back to constructing fresh otherwise. To refresh the embedded prompts after editing template code in `prompts.py`, re-run `python <task>/eval*/populate_prompts.py` (idempotent).

### 3.1 VOI — `placements`

Model `FINAL_JSON` payload and dataset `answer` field:

```json
{
  "placements": [
    {"shape": "S1", "angle": 180, "vertex": "V2", "grid": [4, 2]},
    {"shape": "S2", "angle":  90, "vertex": "V3", "grid": [5, 2]}
  ]
}
```

- `shape` — string, must equal an inventory shape id from the task JSON.
- `angle` — integer, one of `{0, 90, 180, 270}` (clockwise rotation around local origin).
- `vertex` — string, the post-rotation vertex id.
- `grid` — `[int, int]`, global grid coordinate the chosen vertex maps to.
- Each shape may be used **at most once**. Order of placements is irrelevant for scoring.

### 3.2 cube1 — `faces`

```json
{
  "faces": {
    "TOP":    {"patternId": "smile",    "rotation":  90},
    "BOTTOM": {"patternId": "triangle", "rotation":  90},
    "FRONT":  {"patternId": "5",        "rotation": 180},
    "BACK":   {"patternId": "?",        "rotation":   0},
    "LEFT":   {"patternId": "?",        "rotation":   0},
    "RIGHT":  {"patternId": "?",        "rotation":   0}
  }
}
```

- All six face keys are required, exactly: `TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT`.
- `patternId` — string. Must come from the task's `allowed_pattern_ids` list, or the literal `"?"` if the face cannot be uniquely determined.
- `rotation` — integer, one of `{0, 90, 180, 270}`.
- For `patternId == "?"`, `rotation` must be `0` (sentinel pair).

### 3.3 cube2 — `directions`

```json
{
  "directions": ["N", "E", "S"]
}
```

- `directions` — array of direction tokens, each one of `{"N", "S", "E", "W"}` (roll up / down / left / right).
- Length ≤ task-defined `MAX_DIRECTION_STEPS`.
- Open-ended: any sequence that produces the target top face is valid; the engine validates by simulation.
- Dataset `answer` stores **one known-valid reference sequence** for solver-coverage statistics.

### 3.4 cutRope — `commands`

```json
{
  "commands": "cut_rope 2\npop_bubble 3\ncut_rope 1 when candy_still for 0.3",
  "reason":   "drop candy onto the upper rope swing, then release after the bubble pop",
  "confidence": 0.85
}
```

- `commands` — string, one command per line. Vocabulary is fixed (see prompt's section 5).
- `reason` — short string (~one sentence) explaining intent.
- `confidence` — float in `[0, 1]`.
- Validator runs the headless replayer; multiple correct command scripts are valid.
- Dataset `answer` stores one known-valid script with `confidence: 1.0` and `reason: "reference solution"`.

### 3.5 lamp — `actions`

```json
{
  "actions": [
    {"joint": 1, "angle":  -60},
    {"joint": 2, "angle": -135},
    {"joint": 3, "angle":  140},
    {"joint": 4, "angle":  -15},
    {"joint": 5, "angle":  165}
  ]
}
```

- `actions` — array of length equal to the task's `segment_count`, no missing joints.
- `joint` — 1-indexed integer matching the segment id in `INPUT FIELDS`.
- `angle` — integer in degrees, in the task's allowed `[angleMin, angleMax]` range, multiple of `angleStep`. Absolute angle measured from the positive x-axis (NOT cumulative across joints).

## 4. Authoring rules

- Length: each task's full system+user prompt should land in a similar size envelope. Target 600–900 words for the user prompt, ±20%. Avoid one task being 200 words and another 1500 — section density must feel comparable.
- Section headers: the literal strings `## 1. TASK`, `## 2. WORLD MODEL`, … `## 9. FINAL INSTRUCTION` are copy-pasted verbatim across all five prompt files.
- "Solving advice" (section 7) must be **task-class generic**, not instance-specific. Never say "for this level, try …".
- Never include the gold answer inside the prompt, even by paraphrase.
- Multimodal images/video are attached **after** the user prompt text, each preceded by a one-line text caption identifying what the asset is.

## 5. Where to put the builder

Each task ships its own `prompts.py` in its own eval directory:

| Task | Prompt file |
|---|---|
| VOI | [VOI/eval/prompts.py](../VOI/eval/) |
| cube1 | [cube1/eval-thinking/prompts.py](../cube1/eval-thinking/) |
| cube2 | [cube2/eval-thinking/prompts.py](../cube2/eval-thinking/) |
| cutRope | [cutRope/eval/prompts.py](../cutRope/eval/) |
| lamp | [lamp/eval-thinking/prompts.py](../lamp/eval-thinking/) |

Each `prompts.py` exposes exactly three functions:

```python
def build_system_prompt() -> str: ...
def build_user_prompt(task) -> str: ...
def build_messages(task, *, project_root) -> list[dict]: ...   # OpenAI-compatible chat messages
```

The five files do not import from each other.
