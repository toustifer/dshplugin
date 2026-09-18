# dshplugin — 让 DSH 里的模型用 Manim 现做动画来解释回答

纯文本在两类内容上会失效：**时序**（谁先谁后、一步怎么变成下一步）和**空间关系**（谁包含谁、哪里变大变小）。这个项目给 DSH 装上能力：回答里直接插入一段模型自己现做的 Manim 动画，把关系与过程画出来。

它是三个组件：

| 组件 | 目录 | 职责 |
|---|---|---|
| **渲染引擎** | `manim-mcp/` | 一个 stdio MCP 服务，向模型暴露 8 个工具：4 个声明式模板（公式推导 / 函数图像 / 流程结构 / 左右对照）、1 个任意代码逃生口、以及 `check` / `style_guide` / `runs`。负责把模板编译成 Manim 源码、调用 Manim 渲染、后处理成 GIF/WebP/PNG 预览、把失败解析成带行号与修法的结构化诊断。 |
| **动画库面板** | `dsh-manim-gallery/` | 一个 DSH 原生插件，注册一个**右侧栏 tab**（页面型，`kind: manim-gallery`）：网格预览全部历史动画、搜索筛选排序、点开用 `<video controls>` 看 MP4。**只读**。入口只有**会话头部右上角**的一个图标按钮；点击后 `sidebarRight.openTab` 让右栏**在旁边展开**，不占用主区、不覆盖页面。左侧栏入口与全页版面板都已移除。 |
| **媒体发布服务** | `media-mcp/` | 一个独立的 stdio MCP 服务，仅依赖 Python 标准库，向模型暴露 `publish_file` 工具：校验路径、嗅探 MIME、生成同源引用、对 PDF 光栅化前 3 页作为图预览，返回通用媒体信封。 |
| **媒体卡片渲染** | `dsh-media-view/` | 一个 DSH 原生 client 插件，注册 `tool.call.toolview`（key = `mcp__media__publish_file`）：在对话流里按模态内嵌播放视频、音频、显示图片与 PDF 多页预览，或提供右侧栏打开按钮。 |
| **行为层** | `skills/manim-explainer/SKILL.md` | 教会模型：什么时候画、选哪个工具、画砸了怎么自愈、以及硬性要求（非空时必须原样贴 `previewMarkdown`、图前后各一句点明关系、一轮最多一张）。 |

产物落在 `renders/`，每条 run 一个目录，含 `scene.py`（可复现可再编辑）、`out/`（mp4/gif/png）、`run.json`；根部的 `renders/index.json` 是面板的数据源。

### 动画会在两个地方出现

1. **回答正文里**（主要方式）。工具返回的 `previewMarkdown` 是一段 Markdown 图片引用，模型把它贴进正文，动画就内嵌在回答里。
2. **工具卡片里**。同一次调用的结果里带一个 image 块，无需模型配合。

正文那条通道对路径形式很挑，值得单独说明，因为它踩过两次坑：

前端只接受 `http(s)://`，或以 `/` 开头且不以 `//` 开头的目标；Host 用 `node:path.resolve` 解析。**对以 `/` 开头的实参，`resolve` 会丢弃 cwd 的目录、只取它的盘符**：

| 引用形式 | `resolve` 结果 | |
|---|---|---|
| `/path/to/project/renders/r1/out/S.gif` | `D:\path\to\project\renders\r1\out\S.gif` | ✅ |
| `/renders/r1/out/S.gif` | `D:\renders\r1\out\S.gif` | ❌ |
| `/D:/path/to/project/renders/r1/out/S.gif` | `D:\D:\path\to\project\...` | ❌ |

所以引擎发出的是「**去掉盘符的完整绝对路径**」，而 `install.ps1` 唯一要做的就是让文件系统 provider 的 cwd 落在**与渲染产物同一个盘符**上——它把 `fs-sandbox.cwd` 钉到 `renders/` 的父目录，目录本身无关紧要，盘符才是关键。换盘符安装时会重新钉。

验证这条通道可以随时跑（它用本机 browser-session secret 签一个真 cookie，直接问运行中的 Host 要字节）：

```powershell
$c = Get-Content "$env:USERPROFILE\.dsh\.credentials.yaml" -Raw
$env:DSH_SECRET = [regex]::Match($c,'client-connection/browser-session:[\s\S]*?secret:\s*(\S+)').Groups[1].Value
node tests/manual/probe_file_api.mjs
```

---

## 安装

### 方式一：DSH 插件市场 / npm 安装独立组件（推荐）

本仓库的核心组件现已独立发布到 npm 官方注册表，支持在 DSH 桌面端或通过 CLI 独立受管安装：

- **媒体视图渲染器 (`dsh-media-view`)**：
  ```bash
  dsh plugin --profile web add dsh-media-view
  ```
  在 `<dshHome>/profiles/web/cordis.patch.yml` 中追加：
  ```yaml
  - insert:
      - id: media-view
        name: 'dsh-media-view'
  ```

---

### 方式二：全套全家桶源码一键安装（含 Manim 渲染引擎与本地面板）

```powershell
cd <path-to-dshplugin>

.\install.ps1 -DryRun     # 先看它打算做什么。dry-run 不写任何文件。
.\install.ps1             # 真正安装
```

然后**必须重启 dsh web**：

```powershell
& "$HOME\.dsh\restart-web.ps1"
```

重启后应该看到：会话头部右上角多出一个「动画库」图标，点它右栏会在旁边展开（不覆盖页面）；问一个值得画的问题（「为什么 e^{iπ} + 1 = 0」这类），回答正文里会内嵌一段会动的图。

## 卸载

```powershell
.\uninstall.ps1 -DryRun
.\uninstall.ps1
```

`renders\` **默认保留**（那些是你的作品）；要一起删加 `-PurgeRenders`。

---

## 它改了你 profile 里的哪两样东西

安装器只动两个文件，两个都会先备份成 `.bak-<时间戳>`：

| 文件 | 改动 |
|---|---|
| `~/.dsh/profiles/web/cordis.patch.yml` | 追加一个 `- insert:` 条目（`id: mcp-manim`），挂载 MCP。**保留文件里原有的全部注释**——所以它做的是按行定位的文本手术，不是 YAML 反序列化再序列化（那会吃掉注释）。 |
| `~/.dsh/profiles/web/package.json` | `dsh.profile.bundles` 数组追加 `"dsh-manim-gallery"`；`dependencies` 追加指向插件目录的 `link:` 项。 |

另外它会：

- 把 `dsh-manim-gallery/` 复制到 `~/.dsh/plugins/dsh-manim-gallery/`，并把其中 `lib/client.js` 的 `RENDER_ROOT` 改写成与 MCP 的 `MANIM_MCP_RENDER_ROOT` 一致（面板与引擎必须指向同一个根）；
- 在 `~/.dsh/profiles/web/node_modules/` 建一个指向插件目录的符号链接；
- 把 `skills/manim-explainer/` 复制到 `~/.dsh/skills/manim-explainer/`。

**卸载后这两个配置文件会逐字节还原**——这条有测试钉住（`tests/test_installer_apply.py` 的往返一致断言）。

### 为什么安装器是「PowerShell 薄壳 + Python 核心」

`install.ps1` / `uninstall.ps1` 只做参数解析、依赖体检和转述；所有会改文件的逻辑在 `tools/dsh_installer.py` 里，因为那是**可以被 pytest 精确断言**的地方。它改的是你的 profile，出错代价高，值得放在能断言的层。`-DryRun` 会把完整计划打成 JSON。

---

## 依赖

| 依赖 | 本机实测 | 验证命令 |
|---|---|---|
| Python | 3.13.5（`D:\ProgramData\anaconda3\python.exe`） | `python -V` |
| Manim Community | v0.20.1 | `manim --version` |
| MiKTeX | 24.1（`latex` / `dvisvgm` 可用） | `where latex` |
| FFmpeg | 可用（`palettegen`/`paletteuse` 齐备） | `ffmpeg -version` |
| Python MCP SDK | `mcp` 与 `fastmcp` 均已安装 | `python -c "import mcp, fastmcp"` |
| Node（仅跑面板测试） | v22.21.1 | `node --version` |

`install.ps1` 会对前四项做体检，缺哪个都会明确警告（不会静默装下去）。

---

## 跑测试

```powershell
# 引擎 + 安装器 + Skill 文档不变量
D:\ProgramData\anaconda3\python.exe -m pytest

# 面板（纯 Node 离线，不需要浏览器、不需要 DSH 在跑）
cd dsh-manim-gallery
node --test "test/*.test.mjs"
```

真机验收脚本（需要 Manim/FFmpeg 真的可用）：

```powershell
D:\ProgramData\anaconda3\python.exe manim-mcp\server.py --selftest
D:\ProgramData\anaconda3\python.exe tests\manual\render_templates.py
D:\ProgramData\anaconda3\python.exe tests\manual\stdio_smoke.py
D:\ProgramData\anaconda3\python.exe tests\manual\acceptance_tools.py
D:\ProgramData\anaconda3\python.exe tests\manual\export_last_frames.py   # 导出各模板末帧供目视检查
```

> **改动 `manim-mcp/manim_mcp/scenes/` 之后必须跑 `render_templates.py` 并目视看导出的末帧。** 单元测试只能断言「源码里有没有某个名字」；`json.dumps(None)` 生成 `null`（`ast.parse` 通过、Manim import 时 `NameError`）、抛物线越出坐标区穿过标题、箭头穿过方框、标签挂到错误的分支上——这些缺陷**全部**是真机渲染加目视检查发现的。

---

## 排错

| 现象 | 先看哪里 |
|---|---|
| 对话里不出动画 | 先跑 `manim-mcp\server.py --selftest`，它会把依赖与渲染链一次性验完并给出退出码 |
| 工具列表里没有 `mcp__manim__*` 或 `mcp__media__*` | `failOnStartupError: true` 会让 MCP 启动失败显式暴露。看 dsh 启动日志里的 `mcp-client(manim)` 或 `mcp-client(media)` |
| 发布文件后卡片空白/未渲染 | 检查插件是否注册 `mcp__media__publish_file`，跑 `media-mcp\server.py --doctor` 查看环境路径 |
| 图片位置是空的/裂图 | 跑 `node tests\manual\probe_file_api.mjs`。它对运行中的 Host 实测那条引用，能直接区分「路径形式不对」「`fs-sandbox.cwd` 没钉在同一个盘符」「产物被删了」「鉴权没带上」 |
| 面板能打开但读不到数据 | 面板会显示它**尝试读取的绝对路径**。核对它与 MCP 的 `MANIM_MCP_RENDER_ROOT` 是否一致 |
| 缩略图空白 | 在**已登录的浏览器**里打开 `/api/file?path=…`。401 = 鉴权没带上；404 = 产物被删了 |
| 公式渲染报错 | `where latex`；MiKTeX 首次编译宏包很慢，冷启动一次约 35 秒 |
| 中文变成方框 | `manim-mcp\manim_mcp\style.py` 的字体探测；`style_guide` 工具会把本机可用字体名列出来 |

---

## 文档索引

- **设计文档**：
  - `docs/superpowers/specs/2026-09-12-manim-visual-explainer-design.md`（动画引擎与动画库设计）
  - `docs/superpowers/specs/2026-09-14-media-publish-channel-design.md`（通用多模态文件发布通道设计）
- **实施计划**：
  - `docs/superpowers/plans/2026-09-12-manim-mcp-engine.md`（渲染引擎，已执行完毕，末尾有 20 条偏离记录）
  - `docs/superpowers/plans/2026-09-12-manim-gallery-panel.md`（面板，已执行完毕）
  - `docs/superpowers/plans/2026-09-12-manim-skill-and-install.md`（安装接入与验收）
  - `docs/superpowers/plans/2026-09-14-media-publish-channel.md`（通用多模态文件发布实施计划）

## 边界

- 面板**只读**：不做删除、不做重渲染。手写的打包插件没有 client→host 调用通道（那需要 Typert Gateway 的生成式 Remote 与完整 TS 构建管线），所以写操作改由 MCP 侧的 `runs` 工具承担。
- 用社区版 Manim，不是 3b1b 的 ManimGL 分支。
- 不做语音合成、多段视频剪辑、云端上传。
