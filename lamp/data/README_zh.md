# lamp 数据

**语言：[English](README.md) | 中文（本文件）**

`levels/` 和 `images/` 这两个子目录**不在 git 里**——它们托管在 HuggingFace，按需下载到本目录。

## 拉数据

从项目根运行：

```bash
pip install -U huggingface_hub
python scripts/download_dataset.py --tasks lamp
```

跑完后此目录长这样：

```
lamp/data/
├── levels/
│   ├── manifest.json
│   ├── lamp-000.json
│   ├── ...
│   └── lamp-609.json   （610 个关卡）
└── images/
    ├── lamp-000.png
    ├── ...
    └── lamp-609.png
```

HuggingFace 源：<https://huggingface.co/datasets/Sayaka123/simverse2026>（双盲匿名版）。

## Per-record schema

每个 `levels/lamp-XXX.json` 都遵循 SimVerse v1 schema，包含 `prompt.{system,user}`、`answer.actions`，以及任务原生字段（`workspace`、`arm`、`target`、`obstacles` 等）。锁定的标答 schema 见 [`docs/PROMPT_SKELETON.md`](../../docs/PROMPT_SKELETON.md) §3.5。
