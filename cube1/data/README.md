# data 目录说明

**语言：[English](README_en.md) | 中文（本文件）**

`data/` 只保存测评数据，不承担代码逻辑。

> ⚠️ **`data/task_jsons/`、`data/images/`、`data/manifests/` 不在 git 里**——它们托管在 HuggingFace。从项目根运行：
>
> ```bash
> pip install -U huggingface_hub
> python scripts/download_dataset.py --tasks cube1
> ```
>
> HF 源（双盲匿名）：<https://huggingface.co/datasets/Sayaka123/simverse2026>

下载后此目录会变成：

- `data/task_jsons/`
  - 每道题对应一个任务 JSON
- `data/images/blank_nets/`
  - 空白十字展开图图片
- `data/images/path_sequences/`
  - 路径图图片
- `data/manifests/reconstruct_tasks.jsonl`
  - 批量测评时使用的任务清单

## 重新生成数据

如果你修改了关卡、图片样式或任务描述，可以重新生成测评数据：

```powershell
python eval/build_eval_assets.py --input levels/reconstruct
```

## 相关脚本

真正使用这些数据的脚本都在 `eval/` 目录：

- `eval/build_eval_assets.py`
- `eval/eval_local.py`
- `eval/run_sampled_eval_local.py`
- `eval/summarize_model_results.py`

## 模型配置

模型名称、API 地址、API Key、超时等配置写在：

- `eval/eval_common.py`
