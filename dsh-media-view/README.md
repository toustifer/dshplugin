# dsh-media-view

> DeepSeek Harness (DSH) 原生会话内多模态媒体播放与翻页阅读器。

[![npm version](https://img.shields.io/npm/v/dsh-media-view.svg)](https://www.npmjs.com/package/dsh-media-view)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![dsh-plugin](https://img.shields.io/badge/DSH-plugin-4b32c3.svg)](https://github.com/toustifer/dshplugin)

解决 DeepSeek Harness 智能体产出媒体文件（视频、音频、PDF、图片）后无法在对话流内直接预览的痛点。

---

## ✨ 核心能力

- 🎬 **视频原生播放**：会话消息流内直接内嵌 `<video controls>` 原生播放器，无需跳转外部应用；
- 🎵 **音频播放支持**：内嵌 `<audio controls>` 播放生成的配音、音效或语音；
- 📄 **PDF 多页光栅化预览**：自动渲染 PDF 前 3 页缩略图供翻页阅读，附带一键全量查看操作；
- 🖼️ **高清图像原生呈现**：原生呈现模型生成的各种高保真图表、绘图产物；
- 🛡️ **优雅容错与安全沙箱**：针对超限、无效或缺失文件自动降级展示安全状态与操作提示。

---

## 📦 安装与启用 (DeepSeek Harness)

### 方式一：DSH 插件市场 / CLI 安装（首推）

插件已正式发布至 npm 官方注册表并在 DSH 市场建立索引：

1. **命令行直接添加**：
   ```bash
   dsh plugin --profile web add dsh-media-view
   ```

2. **配置启用**（在 `<dshHome>/profiles/web/cordis.patch.yml` 中追加）：
   ```yaml
   - insert:
       - id: media-view
         name: 'dsh-media-view'
   ```

3. **重启或热载 DSH Web**：
   在会话中由模型调用 `mcp__media__publish_file` 发布的文件将自动以内嵌卡片呈现。

---

## 🛠️ 技术规范与开发

- **运行平台**：DeepSeek Harness Web GUI
- **注入服务**：`@deepseek-ai/dsh-api-remotes`, `@deepseek-ai/dsh-client-ui-renderer`, `@deepseek-ai/dsh-client-ui-layout`
- **挂载点**：注册 `tool.call.toolview` (key: `mcp__media__publish_file`)
- **测试覆盖**：
  ```bash
  npm test
  # 17 项单元测试 100% 绿灯 (node --test)
  ```

---

## 📄 开源协议

MIT License © 2026 toustifer
