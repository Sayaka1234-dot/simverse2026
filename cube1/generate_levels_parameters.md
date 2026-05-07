# `generate-levels.js` 参数说明

本文档简要说明当前还原关卡生成脚本里的核心参数。

## 基础方向参数

- `DIRS`
  - 允许的滚动方向集合
  - 当前为：`N`、`S`、`E`、`W`

- `ROTATIONS`
  - 图案允许的旋转角度
  - 当前为：`0`、`90`、`180`、`270`

## 图案池

- `PATTERN_POOL`
  - 随机关卡使用的候选图案集合
  - 当前包含：
    - 数字 `1` 到 `9`
    - 字母 `A` 到 `Z`
    - 简单图案：`smile`、`star`、`heart`、`arrow_up`、`arrow_right`、`arrow_down`、`arrow_left`、`circle`、`triangle`、`square`、`diamond`、`plus`

如果要增加新图案：

1. 把图案 ID 加到 `PATTERN_POOL`
2. 在前端图案渲染逻辑里补上对应绘制方式

## 难度分层

- `TIERS`
  - 定义不同难度层的步数范围和数量

常见字段：

- `difficulty`
  - 难度编号
- `minMoves` / `maxMoves`
  - 本层关卡允许的最小和最大滚动步数
- `count`
  - 该层生成的关卡数量

## 随机种子

脚本支持固定种子生成，便于复现：

```powershell
node generate-levels.js --seed=12345
```

## 关卡合格性检查

生成时会排除一些过于简单或结构不合理的路径，例如：

- 同一方向连续滚动过多次
- 只在很少的格子里来回重复
- 暴露出的可推理面太少
- 观测图案变化过少

## 重新生成关卡

```powershell
node generate-levels.js
```

生成后建议立即执行：

```powershell
node validate-levels.js
```

这样可以确保新关卡能通过真实引擎验证。
