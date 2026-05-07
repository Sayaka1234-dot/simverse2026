# Cut the Rope: H5DX

<p align="center">
<img src="./images/ctr_pattern.webp" alt="Cut the Rope: H5DX Logo" width="400"/>
</p>

## 项目简介

*Cut the Rope: H5DX (HTML5 Deluxe)* 是一个基于网页版本 *Cut the Rope* 的民间增强项目，原作由 ZeptoLab 开发。这个项目的目标是改进原始代码、加入新功能，并提升整体游玩体验。

本项目所使用的游戏源码主要来自 Firefox OS 版本，该版本包含较完整的源代码，这也为当前项目的持续开发提供了基础。

目前项目主要由 [yell0wsuit](https://github.com/yell0wsuit) 维护。

> [!NOTE]
> 本项目与 ZeptoLab 没有任何官方关联，也不会获得官方背书。原游戏及其素材的所有权利均归 ZeptoLab 所有。

### 相关项目

- [Cut the Rope: DX](https://github.com/yell0wsuit/cuttherope-dx)：该项目是本作的 C# 反编译版本，目前正在持续开发中，目标是与 HTML 版本保持一致。

## 在线体验

你可以通过以下地址在线游玩：

<https://yell0wsuit.github.io/cuttherope-h5dx/>

## 主要特性

- 使用 [TypeScript](https://www.typescriptlang.org/) 编写，并进行了完整类型化（参见 [PR #32](https://github.com/yell0wsuit/cuttherope-h5dx/pull/32)）
- 全新的加载系统
- 新增盒子内容：Spooky Box、Steam Box
- 移植 *Holiday Gift* 关卡、素材与动画，以及 Paddington 主题资源
- 增加更多游戏内音乐，并支持随机播放
- 分辨率最高支持 HD 1080p，可适配当前屏幕尺寸
- 支持每个盒子超过 25 个关卡
  - 已加入 Buzz Box 中来自 Round 5 活动的额外 25 个关卡（参见 [PR #33](https://github.com/yell0wsuit/cuttherope-h5dx/pull/33)）
- 修复了一些音频与音乐相关问题，详情可见 [PR #9](https://github.com/yell0wsuit/cuttherope-h5dx/pull/9)
- 支持从 [TexturePacker](https://www.codeandweb.com/texturepacker) 的 JSON 数组格式加载自定义贴图与动画，便于模组制作与新资源扩展

## 项目目标

### 长期目标

- [ ] **修复 Bug 与整体打磨**：持续修复问题，提升整体稳定性与体验。
- [ ] **代码优化与现代化**：优化性能关键路径，并逐步现代化代码结构。
- [ ] **可选目标**：增加更多功能，例如 ~~关卡编辑器~~\*、自定义关卡管理器等。

\* 可改用 <https://adriandrummis.github.io/CutTheRopeEditor/>，因为将关卡编辑器直接集成到当前引擎中的复杂度较高。

## 开发与贡献

*Cut the Rope: H5DX* 仍在持续开发中，欢迎参与贡献。如果你希望一起完善这个项目，可以参考以下方式：

- **反馈问题**：如果你发现 Bug 或其他异常，请前往 [GitHub Issues](https://github.com/yell0wsuit/cuttherope-h5dx/issues) 提交问题。
- **功能建议**：如果你有新功能或改进想法，也可以通过 Issues 提交建议。
- **代码贡献**：如果你希望直接参与开发，请 fork 仓库并提交 pull request。

### 本地测试

如果你想在本地运行并测试项目，可以按以下步骤进行：

1. 确保本机安装了较新的 [Node.js](https://nodejs.org/) 版本，建议使用 v20 或更高版本。
2. 克隆仓库：

   ```bash
   git clone https://github.com/yell0wsuit/cuttherope-h5dx.git
   cd cuttherope-h5dx
   ```

   如果你更习惯图形界面，也可以使用 [GitHub Desktop](https://desktop.github.com/) 进行克隆。

3. 安装依赖：

   ```bash
   npm install
   ```

4. 启动本地开发服务器：

   ```bash
   npm run dev
   ```

5. 在浏览器中打开终端输出的本地地址即可开始测试。默认通常是：

   ```text
   http://localhost:5173/
   ```

开发模式下，所有盒子与关卡默认都会解锁，因此你不需要从头通关，就可以直接测试指定关卡。
