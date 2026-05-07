# Cube2 (Goal-Roll Top Face)

`cube2/` is a standalone top-face target variant of the cube project.

The web app, task data, images, and `eval-thinking` pipeline now run from paths inside
`cube2/` only. No parent-directory `data2` fallback or external CDN runtime is required.

## Gameplay

- You are given the visible cross net of the cube's unfolded outer surface.
- The number under each visible face is the clockwise rotation in degrees from the original upright pattern.
- You are also given a target image for the final top face.
- Your goal is to output or design any valid roll sequence so that the cube's top face, viewed from above at the end, matches the target exactly.

## Data

- Tasks: `cube2/data2/task_jsons/*.json`
- Manifest: `cube2/data2/manifests/goal_roll_tasks.jsonl`
- Sampled manifest: `cube2/data2/manifests/sampled_150_seed20260425.jsonl`
- Images: `cube2/images/<LEVEL_CODE>/initial_net.png` and `cube2/images/<LEVEL_CODE>/target_top_face.png`
- Source snapshot for regeneration: `cube2/source_data/task_jsons/*.json`

## Regenerate

```powershell
python cube2\generate_goal_roll_dataset.py
python cube2\retarget_data2_dataset.py
```

## Run The Web App

```powershell
cd cube2
python -m http.server 8003
```

Open:

```text
http://127.0.0.1:8003/
```

The port 8003 matches the convention in the top-level [README](../README.md) so the five SimVerse task demos can run in parallel without clashing.
