# lamp data

**Languages: English (this file) | [中文](README_zh.md)**

The `levels/` and `images/` subdirectories of this folder are **not committed to git**. They are hosted on HuggingFace and downloaded into this directory on demand.

## Get the data

From the project root, run:

```bash
pip install -U huggingface_hub
python scripts/download_dataset.py --tasks lamp
```

After that, you should see:

```
lamp/data/
├── levels/
│   ├── manifest.json
│   ├── lamp-000.json
│   ├── ...
│   └── lamp-609.json   (610 levels)
└── images/
    ├── lamp-000.png
    ├── ...
    └── lamp-609.png
```

The HuggingFace source: <https://huggingface.co/datasets/SimVer-ano/simverse2026> (anonymized for double-blind review).

## Per-record schema

Each `levels/lamp-XXX.json` has the SimVerse v1 schema with `prompt.{system,user}`, `answer.actions`, plus task-native fields (`workspace`, `arm`, `target`, `obstacles`, etc.). See [`docs/PROMPT_SKELETON.md`](../../docs/PROMPT_SKELETON.md) §3.5 for the locked answer schema.
