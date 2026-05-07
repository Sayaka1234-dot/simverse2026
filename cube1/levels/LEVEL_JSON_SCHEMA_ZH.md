# 关卡 JSON 字段说明

本文档说明当前“立方体还原”模式的关卡 JSON 结构，以及各字段在出题、判分和验证中的作用。

## 1. 顶层字段

- `id`
  - 关卡编号
- `code`
  - 关卡代码，例如 `C001`
- `name`
  - 关卡名称
- `description`
  - 关卡简短说明
- `netLayout`
  - 展开图布局，当前固定为 `standard_cross`
- `netFaces`
  - 展开图六个面的原始图案信息
- `netPatterns`
  - 展开图图案的简化列表
- `path`
  - 路径方向序列
- `startX` / `startY`
  - 路径起点坐标
- `gridWidth` / `gridHeight`
  - 路径棋盘尺寸
- `difficulty`
  - 难度等级
- `moveCount`
  - 滚动步数
- `tier`
  - 难度层
- `tierLabel`
  - 难度层文本标签
- `prompt`
  - 题面数据
- `answers`
  - 标准答案与验证真值

## 2. `prompt` 字段

`prompt` 是玩家直接看到，或前端渲染题面时需要的数据。

### `prompt.directions`

滚动方向序列，例如：

```json
["N", "E", "S"]
```

含义：

- `N`：向上滚
- `S`：向下滚
- `E`：向右滚
- `W`：向左滚

### `prompt.observedPathFaces`

路径上的俯视图案序列。每一项表示立方体滚动到某一步后，从正上方向下看路径格子时看到的图案状态。

单项结构：

```json
{
  "patternId": "triangle",
  "rotation": 180,
  "flipHorizontal": false,
  "flipVertical": true
}
```

字段含义：

- `patternId`
  - 图案 ID
- `rotation`
  - 图案旋转角度，只允许 `0 / 90 / 180 / 270`
- `flipHorizontal`
  - 是否做左右翻转
- `flipVertical`
  - 是否做上下翻转

### `prompt.slotSequence`

路径推理过程中，依次暴露到的面位序列。

### `prompt.requiredSlots`

从 `slotSequence` 去重后得到的结果，表示这道题至少可以推出哪些面。

### `prompt.requiredCount`

等于 `requiredSlots.length`。

## 3. `answers` 字段

### `answers.solutionFaces`

玩家应填写的标准答案。

规则：

- 能唯一推出的面，给出真实 `patternId` 和 `rotation`
- 无法唯一推出的面，写成：

```json
{
  "patternId": "?",
  "rotation": 0
}
```

### `answers.trueSolutionFaces`

真实完整立方体答案，供验证器使用。

和 `solutionFaces` 的区别：

- `solutionFaces` 面向玩家判分
- `trueSolutionFaces` 面向引擎验证和回放

### `answers.bottomFaces`

真实滚动过程中，每一步处于底面的外表面信息。

## 4. 为什么有些面是 `?`

如果路径观测不足，某些面无法唯一确定，那么标准答案必须写成 `?`。

这表示：

- 玩家也应该填 `?`
- 这些面不要求填写方向
- 判分时只检查玩家是否也填了 `?`

## 5. 生成与验证闭环

一条合法关卡的生成流程大致是：

1. 随机生成一个真实立方体
2. 随机生成滚动路径
3. 用真实引擎逐步滚动
4. 记录 `prompt.observedPathFaces`
5. 推出玩家应填写的 `answers.solutionFaces`
6. 保留真实答案 `answers.trueSolutionFaces`
7. 用验证器再次回放，确认题面和答案一致

## 6. 判分时重点使用哪些字段

- 题面渲染：
  - `prompt.directions`
  - `prompt.observedPathFaces`
- 玩家答案判分：
  - `answers.solutionFaces`
- Debug 与验证器回放：
  - `answers.trueSolutionFaces`
