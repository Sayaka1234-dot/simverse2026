# data2

**语言：[English](README.md) | 中文（本文件）**

> ⚠️ **`task_jsons/`、`manifests/`、`index.json` 不在 git 里**——它们托管在 HuggingFace。克隆完仓库后运行：
>
> ```bash
> pip install -U huggingface_hub
> python scripts/download_dataset.py --tasks cube2
> ```
>
> HF 源（双盲匿名版）：<https://huggingface.co/datasets/Sayaka123/simverse2026>

本目录存放重新生成的 `cube2` 任务（顶面目标 gameplay）。

## 任务定义

- 输入：立方体外表面展开图（十字形）
- 每个可见面下方的数字是该面相对原始竖直 pattern 顺时针旋转的角度
- 目标：输出一个滚动序列，使立方体最终顶面（从上往下看）与目标图案完全一致
- 多个序列可能都正确。Validator 决定是否合法

## 目录结构

- `task_jsons/`：每个任务一个 JSON 文件
- `manifests/goal_roll_tasks.jsonl`：完整任务清单
- `manifests/sampled_150_seed20260425.jsonl`：测评固定的采样清单
- `index.json`：web app 用的数据集概览
- `../images/<LEVEL_CODE>/`：成对的初始展开图和目标顶面图
- `../source_data/task_jsons/`：用于重建数据集的源快照

## 重新生成

```powershell
python cube2\generate_goal_roll_dataset.py
python cube2\retarget_data2_dataset.py
```
