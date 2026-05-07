# 还原模式关卡目录说明

当前项目只保留“立方体还原”模式，关卡源文件位于：

- `levels/reconstruct/`

## 修改关卡后的注意事项

当你新增、删除或手动修改关卡 JSON 后，需要重新执行：

```powershell
node validate-levels.js
```

这一步会做两件事：

1. 用真实立方体滚动引擎校验关卡数据是否自洽
2. 重建运行时索引：
   - `levels/index.json`
   - `levels/catalog.generated.js`

页面实际加载的是重建后的索引，而不是直接扫描文件夹。所以如果你删掉某个 JSON，但没有重新执行校验脚本，页面里仍然可能显示旧索引中的关卡。

## 题面视角约定

`prompt.observedPathFaces` 表示的是：

- 立方体按 `prompt.directions` 给出的路径滚动
- 每滚动一步后，从立方体正上方向下观察路径格子时看到的图案与朝向

这和玩家填写展开图不是同一件事：

- 题面观测：路径上的俯视图案
- 玩家答案：立方体外表面的展开图图案和方向

两者之间的角度换算由引擎中的固定映射完成，不能把路径图案的朝向直接原样抄到展开图上。

## 固定展开图顺序

项目使用固定十字展开图，`netFaces` 的顺序永远是：

```text
[top, front, right, back, left, bottom]
```

对应到逻辑面位就是：

1. `TOP`
2. `FRONT`
3. `RIGHT`
4. `BACK`
5. `LEFT`
6. `BOTTOM`
