# Manim 可视化解释插件 — 设计方案

- 日期：2026-09-12
- 项目根目录：`D:\myprogram\dshplugin`
- 状态：待用户评审

---

## 1. 背景与目标

大模型在解释数学推导、算法执行、函数行为、流程与结构时，纯文本存在表达上限：读者需要自己在脑中重建时序与空间关系，这正是理解成本最高的部分。

本项目的目标：让 DSH 里的模型有能力**在回答中直接插入一段自己现做的 Manim 动画**，把「关系与过程」画出来，从而降低理解成本。

成功的样子：用户问「快速排序为什么是 O(n log n)」，模型回答里除了文字，还有一段 10 秒动画把分治的递归树一层层长出来。

### 1.1 判据

1. 模型能在一次回答中产出可播放的动画，且**动画直接内嵌显示在对话里**，不需要用户手动打开文件。
2. 从模型决定画到动画出现在对话里，端到端 **≤ 20 秒**（draft 画质）。
3. 模型生成的 Manim 代码首次成功率有保障：失败时能自我修复并重试，最终不静默放弃。
4. 中文与 LaTeX 公式都能正确渲染。

---

## 2. 环境事实（已实测，非推断）

| 依赖 | 实测结果 |
|---|---|
| Python | `D:\ProgramData\anaconda3\python.exe`，3.13.5 |
| Manim Community | v0.20.1，`manim.exe` 在 PATH，`python -m manim` 同样可用 |
| MiKTeX | 24.1，`latex/pdflatex/dvisvgm` 可用；`MathTex` 实测渲染成功 |
| FFmpeg | PATH 上可用，`palettegen` / `paletteuse` 滤镜均存在 |
| Python MCP SDK | `mcp` 与 `fastmcp` **都已安装**，无需额外依赖 |
| 冷启渲染耗时 | 35.3s（首次含 LaTeX 格式与宏包编译） |
| 热态渲染耗时 | 8.7s / 10.8s（同一场景重复渲染） |
| MP4 → GIF 耗时与体积 | 0.5s，800px/15fps，73KB |
| 中文渲染 | `Text(..., font="Microsoft YaHei")` 正确显示，非方框 |
| 公式渲染 | `MathTex(r"e^{i\pi} + 1 = 0")` 正确 |

结论：**全部依赖已就绪，项目是纯软件实现工作，无需安装任何新依赖。**

---

## 3. 边界

### 3.1 做

- 一个独立的 MCP 服务（stdio），向模型暴露「生成+渲染 Manim 动画」的能力。
- 一组高层声明式工具（模型几乎不写 Python）+ 一个任意代码逃生口。
- 渲染产物的后处理（MP4 → GIF/WebP/PNG）与体积控制。
- 失败诊断与自愈提示，让模型能自己修好代码。
- 一个 Skill，规定「什么时候画、怎么画才有效」。
- 幂等的安装/卸载脚本与完整中文文档。

### 3.2 不做（YAGNI）

- 语音合成、字幕、多段视频剪辑拼接。
- ManimGL（3b1b 的私有分支）——社区版 Manim 才是本机可用且文档完善的。
- Web 端可视化编辑器。
- DSH Client 端精美播放卡片（架构留插槽，v2 再做）。
- 视频云端上传/分享。

---

## 4. 总体架构

```
用户提问
   │
   ▼
DSH Agent（模型）
   │  ① Skill「manim-explainer」判断：这一轮要不要画？画什么类型？
   │
   ├──► MCP 工具 mcp__manim__*（serverName = manim，stdio 子进程）
   │        │
   │        ├─ 高层工具：equation / graph / diagram / compare
   │        ├─ 逃生口：render
   │        └─ 辅助：check / style_guide / runs
   │        │
   │        ▼
   │    引擎：模板 → scene.py → manim CLI（子进程）→ MP4
   │        │                                  │
   │        │                                  └─ 失败 → diagnostics → 结构化错误+hint
   │        ▼
   │    后处理：MP4 → GIF（两遍调色板）/ WebP / PNG 海报
   │        │
   │        ▼
   │    返回信封 { ok, runId, assets, previewMarkdown, ... }
   │        │
   │        └─ 同时返回 MCP image 内容块（GIF）→ 对话内直接显示动图
   │
   └──► 模型把 previewMarkdown 贴进回复 → 同源 /api/file 兜底显示
```

两条内嵌显示通道（详见第 12 节）：MCP image 内容块为主，回复内的绝对路径 Markdown 为兜底。**两条独立可用**，任一条失效不影响另一条。

---

## 5. 目录结构

```
D:\myprogram\dshplugin\
├─ README.md                          中文：原理 / 安装 / 用法 / 排错
├─ .gitignore                         忽略 renders/、__pycache__/、*.local.json
├─ install.ps1                        幂等安装（依赖体检 + 配置挂载 + Skill 安装）
├─ uninstall.ps1                      幂等卸载与回滚
├─ manim-mcp\
│  ├─ server.py                       FastMCP(stdio) 入口，注册 8 个工具
│  ├─ config.py                       配置解析（env 优先，其次自动探测，最后默认值）
│  ├─ style.py                        3b1b 配色/字号/节奏常量 + 中文字体探测
│  ├─ engine\
│  │  ├─ __init__.py
│  │  ├─ workspace.py                 run 目录生命周期、命名、保留与清理
│  │  ├─ render.py                    写 scene.py → 调 manim 子进程 → 收产物
│  │  ├─ postprocess.py               MP4 → GIF/WebP/PNG 与体积控制链
│  │  └─ diagnostics.py               stderr/traceback → 结构化错误 + 修复提示
│  ├─ scenes\                         4 个高层模板的 Manim 代码生成器
│  │  ├─ __init__.py                  模板注册表
│  │  ├─ equation.py
│  │  ├─ graph.py
│  │  ├─ diagram.py
│  │  └─ compare.py
│  └─ tools\                          每个 MCP 工具的实现
│     ├─ __init__.py
│     ├─ declarative.py               equation / graph / diagram / compare
│     ├─ render.py                    render
│     ├─ check.py                     check
│     ├─ style_guide.py               style_guide
│     └─ runs.py                      runs
├─ skills\manim-explainer\SKILL.md    行为层（安装时复制到 ~/.dsh/skills/）
├─ renders\                           渲染产物（gitignore，可随时清空）
└─ tests\
   ├─ test_diagnostics.py
   ├─ test_postprocess.py
   ├─ test_workspace.py
   ├─ test_scenes.py
   └─ fixtures\
```

---

## 6. MCP 工具契约

- `serverName`：`manim`
- 模型看到的工具名：`mcp__manim__<rawName>`
- 所有工具都是同步语义（内部 `await` 子进程），不返回「稍后再说」。

工具原始名（raw name）固定为以下 8 个，不接受别名：

| raw name | 类别 |
|---|---|
| `equation` | 高层声明式 |
| `graph` | 高层声明式 |
| `diagram` | 高层声明式 |
| `compare` | 高层声明式 |
| `render` | 逃生口 |
| `check` | 辅助 |
| `style_guide` | 辅助 |
| `runs` | 辅助 |

### 6.1 高层声明式工具（模型不写 Python）

#### `equation` — 公式推导动画

3b1b 招牌形式：多步 LaTeX 逐步变形。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 否 | 顶部标题（中文自动用中文字体） |
| `steps` | string[] | 是 | 每步一个 LaTeX 字符串，2–6 步 |
| `highlight` | string[] | 否 | 与 `steps` 等长，每步要高亮的子串（`\color` 标记） |
| `quality` | enum | 否 | `draft`(默认) / `final` |

#### `graph` — 函数图像

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 否 | 标题 |
| `expressions` | string[] | 是 | 形如 `"x**2"`、`"np.sin(x)"` 的表达式 |
| `x_range` | [number,number,number] | 否 | 默认 `[-4,4,1]` |
| `highlight` | object | 否 | `{point, show_tangent, show_area}` |
| `parameter` | object | 否 | `{symbol, from, to}` 让某参数动态变化 |
| `quality` | enum | 否 | 同上 |

#### `diagram` — 流程 / 结构图

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 否 | 标题 |
| `nodes` | object[] | 是 | `[{id, label, kind: process/decision/terminal/data}]` |
| `edges` | object[] | 是 | `[{from, to, label?}]` |
| `layout` | enum | 否 | `vertical`(默认) / `horizontal` |
| `quality` | enum | 否 | 同上 |

#### `compare` — 左右对照

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 否 | 标题 |
| `left` / `right` | object | 是 | `{title, items: string[]}` |
| `quality` | enum | 否 | 同上 |

### 6.2 逃生口与辅助工具

#### `render` — 任意 Manim 代码

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `code` | string | 是 | 完整 Manim 场景代码，必须含 `from manim import *` 与至少一个 `Scene` 子类 |
| `scene_name` | string | 否 | 指定渲染哪个场景；缺省时取第一个 |
| `quality` | enum | 否 | `draft`(默认) / `final` |
| `preview` | enum | 否 | `gif`(默认) / `webp` / `none` |

#### `check` — 秒级体检（不渲染）

输入 `code`，只做：Python 语法（`ast.parse`）、`from manim import *` 是否存在、是否定义了 `Scene` 子类、场景是否定义了 `construct`。返回 `{ok, issues[]}`。约 0.1 秒，用于在花 10 秒渲染前先挡掉低级错误。

#### `style_guide` — 写代码时的精确事实

无参数。返回本机的：3b1b 调色板精确 hex、可用的中文字体名列表、Manim 0.20.1 的 API 注意事项、一段最小可用代码范式。**不是叙事性指南**（那在 SKILL.md 里），而是写代码时要查的常量与坑。

#### `runs` — 历史与取回

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `action` | enum | 是 | `list` 列出最近 run / `get` 取回某个 run |
| `run_id` | string | `get` 时必填 | |

`get` 返回该 run 的 `scene.py` 源码与产物路径——支持「把刚才那个动画改一下」这类迭代。

### 6.3 统一返回信封

成功：

```json
{
  "ok": true,
  "runId": "20260912-153012-a1b2",
  "sceneName": "Equation",
  "assets": {
    "mp4": "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\Equation.mp4",
    "gif": "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\Equation.gif",
    "poster": "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\Equation.png"
  },
  "previewMarkdown": "![anim](/D:/myprogram/dshplugin/renders/20260912-153012-a1b2/out/Equation.gif)",
  "durationSec": 10.4,
  "renderSeconds": 9.8,
  "gifBytes": 1834231,
  "quality": "draft",
  "warnings": []
}
```

失败：

```json
{
  "ok": false,
  "runId": "20260912-153012-a1b2",
  "stage": "manim",
  "error": {
    "type": "NameError",
    "message": "name 'Circle' is not defined",
    "line": 12,
    "sourceLine": "        c = Circle(radius=1)"
  },
  "hint": "Circle 未被导入。代码开头需要 `from manim import *`。",
  "codePath": "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\scene.py",
  "stderrTail": "..."
}
```

`stage` ∈ `validate` / `python` / `manim` / `postprocess` / `timeout`。

### 6.4 成功时的双内容块

成功返回时，工具结果同时包含：
1. 一个 `text` 块：上面的 JSON 信封（`previewMarkdown` 供模型贴进回复）。
2. 一个 `image` 块：**当前实际生效的预览产物**的 base64，MIME 随产物走——`gif` → `image/gif`，`webp` → `image/webp`，降级到海报帧时 → `image/png`。三者都在 DSH 附件支持的格式表内。

MCP 的 image 块会被 DSH 存入附件并在对话内直接渲染（本 GUI 已实测可行）。

---

## 7. 渲染引擎

### 7.1 run 目录

```
renders\<runId>\
  scene.py      生成或模型提供的代码（可复现、可再编辑）
  media\        manim 中间产物（partial movie files 等）
  out\          最终产物 mp4 / gif / webp / png
  run.json      元数据：工具、参数、耗时、产物、警告
```

- `runId` = `YYYYMMDD-HHMMSS-<4位随机>`。
- 目录名与文件名**只含 ASCII 字母数字与 `-`**：避免空格、括号、中文——它们会破坏 Markdown 图片语法与命令行引号处理。

### 7.2 渲染调用

- 命令：`<python> -m manim render -q<l|m> --format=mp4 --media_dir <run>\media --output_file <Scene> <run>\scene.py <SceneName>`
- 优先用 `sys.executable -m manim`（保证与服务器同一解释器，Manim 一定可导入）；`python -m manim` 会打印一行无害的 `RuntimeWarning`，由诊断层过滤掉。若配置了 `MANIM_MCP_MANIM` 则用该可执行文件。
- 质量档：`draft` → `-ql`（480p15，默认）；`final` → `-qm`（720p30）。
- **不启用 `--disable_caching`**：同一 run 内的重复渲染可复用中间产物。
- 子进程使用 `CREATE_NEW_PROCESS_GROUP`（Windows），超时时用 `taskkill /T /F` 杀整棵进程树。
- 捕获 stdout/stderr 到内存（上限 2MB，超出只留尾部）。

### 7.3 并发、超时与清理

- 并发默认 **1**（`asyncio.Semaphore`）。串行化避免多个 Manim 同时把 CPU 吃满，也避免模型一次发多个动画时互相拖慢。
- 超时默认 **180 秒**，可配。超时返回 `stage: "timeout"` 与已产生的部分 stderr。
- 保留策略：默认保留最近 **50** 个 run，超出的按时间从旧到新删除。清理在每次渲染完成后惰性执行，失败不影响本次渲染。

---

## 8. 后处理与体积控制

### 8.1 GIF 两遍调色板法（已验证）

```
pass 1: ffmpeg -i in.mp4 -vf "fps=15,scale=800:-1:flags=lanczos,palettegen=stats_mode=diff" pal.png
pass 2: ffmpeg -i in.mp4 -i pal.png -lavfi "fps=15,scale=800:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" out.gif
```

### 8.2 体积控制链

目标体积 **8MB**，硬上限 **18MB**（DSH 附件单图上限 20MB，留 2MB 余量）。

按序降级直到达标或降级穷尽：

| 轮次 | fps | 宽度 |
|---|---|---|
| 1 | 15 | 800 |
| 2 | 12 | 800 |
| 3 | 12 | 640 |
| 4 | 10 | 480 |

全部失败 → 改用 **WebP 动图**（同参数），若 WebP 仍超硬顶 → 只输出 **PNG 海报帧**并把 `preview` 指向 PNG，在 `warnings` 里说明原因。

### 8.3 静态场景

若视频总时长 < 1.0 秒，直接输出 PNG 海报帧作为预览（动图无意义）。

### 8.4 海报帧

取**末帧**（`-sseof -0.1`）而非首帧——动画的末帧通常才是结论态，对模型与用户都更有信息量。同时作为 GIF 不可用时的降级预览。

---

## 9. 诊断与自愈

### 9.1 traceback 解析

从 stderr 中定位最后一段 Python traceback，提取：异常类型、消息、`scene.py` 中的行号与该行源码。同时剔除 Manim 的进度条、ANSI 转义、`RuntimeWarning` 噪声。

### 9.2 常见坑映射表

`diagnostics.py` 内置规则表，命中则给出可执行的修复建议：

| 特征 | 给出的 hint |
|---|---|
| `NameError: name 'X' is not defined` | 缺少 `from manim import *`，或拼错了 Manim 类名 |
| 中文显示为方框 | 指定 `font="Microsoft YaHei"` |
| `LaTeX Error` / `Undefined control sequence` | 公式转义问题或使用了不支持的宏，建议改用 `MathTex` 支持的记号 |
| `AttributeError` 涉及 `.animate` | `.animate` 用法错误（应写成 `mob.animate.shift(...)` 并作为 `play` 的参数） |
| `ValueError: ... too many values to unpack` | Mobject 构造参数个数不对 |
| `FileNotFoundError` 涉及 latex/dvisvgm | LaTeX 环境问题，提示检查 MiKTeX |
| 分数/下划线在 `Tex` 中报错 | `Tex` 是文本模式，数学内容要用 `MathTex` |

### 9.3 自愈协议（写进 SKILL.md）

1. 调用 → 失败 → 读 `error.line` 与 `hint`。
2. 只改需要改的地方，重试（**最多 2 次**）。
3. 仍失败 → **不再重试**，改为在回答里用文字/静态图表达，并附上 `codePath` 供排查。
4. **绝不静默放弃，也绝不用「动画生成失败」当作回答的全部内容。**

先用 `check` 挡掉语法级错误，可以把自愈的代价从 10 秒降到 0.1 秒。

---

## 10. 风格系统与中文渲染

### 10.1 风格常量（`style.py`）

写死的取值，模板与 `style_guide` 共用同一份常量，避免两处漂移：

| 项 | 取值 |
|---|---|
| 背景 | `#0E1116`（近黑深灰，3b1b 观感） |
| 主蓝（结构/主体） | `#58C4DD` |
| 强调黄（高亮/结论） | `#FFD166` |
| 正向绿 | `#7BE495` |
| 反向红 | `#FF6B6B` |
| 中性灰（辅助线/坐标轴） | `#5A6472` |
| 正文字号 | 标题 44 / 正文 32 / 注释 24 |
| `play` 默认 `run_time` | 1.0 秒（范围 0.8–1.5） |
| 收尾 `wait` | 0.5 秒（范围 0.3–0.8） |
| 默认总时长 | 8–20 秒 |

- 高亮统一用强调黄；同一画面中强调色只出现一次，避免多点抢注意力。
- 原则：**一个动画只讲一个想法**。
- 代码风格：扁平、避免自定义类与复杂继承，便于模型后续修改。

Manim 社区版自带 `BLUE_B` 等常量与上表色值接近，但**以本表为准**，模板直接写 hex，不依赖 manim 的调色板常量名（避免版本间改名）。

### 10.2 中文字体

Manim 的 `Text` 默认字体不含中文，会渲染成方框。方案：

- `style.py` 启动时探测本机可用的中文字体，优先级：`Microsoft YaHei` → `SimHei` → `Noto Sans CJK SC` → `Source Han Sans SC`。
- 所有模板自动套用探测到的字体；检测不到时在 `warnings` 里提示并回退到 `sans-serif`。
- `style_guide` 工具把**本机实际可用的中文字体名**明确返回给模型，避免模型猜字体名。
- 纯英文/公式场景不强制字体。

---

## 11. Skill 行为层（`manim-explainer`）

### 11.1 触发策略：默认主动

只要这一轮回答存在「关系 / 过程 / 结构」需要表达，**直接画，不询问用户**。典型场景：

- 数学推导、公式证明
- 算法执行过程、数据结构操作
- 函数行为、几何直觉、极限与逼近
- 流程、架构、状态机、因果链
- 错误做法 vs 正确做法的对比
- 用户说「看不懂」「太抽象」「演示一下」时

不画：闲聊、纯事实查询、纯代码编辑、单纯的文件操作、动画明显比一句话更慢的场景。

### 11.2 护栏（不削弱「主动」，但防止失控）

1. **一轮回答最多 1 个动画。** 避免多次渲染拖慢回答，也避免动画淹没重点。
2. **默认 `draft` 画质。** 只有用户明确要「高清 / 最终版」才用 `final`。
3. **渲染失败不影响正文。** 超过重试上限后，正文照常给出，附一句说明与 `codePath`，绝不阻塞回答。
4. **同会话内不重复同一概念的同类动画**，除非用户要求或内容实质不同。

### 11.3 硬性要求

1. 回复里**必须包含 `previewMarkdown`**（否则用户看不到动画）。
2. 图的前后**各写一句话**点明「这张图在说明什么关系」。没有这句，动画只是装饰，不提升理解。
3. 先用 `check` 再 `render`，省掉无谓的 10 秒。

### 11.4 SKILL.md 结构

- 何时画 / 何时不画
- 工具选择决策树（公式 → `equation`；函数 → `graph`；流程结构 → `diagram`；对照 → `compare`；都不合适 → `render`）
- 高层工具的参数速查与示例
- 自愈协议
- 风格红线
- 失败降级话术

---

## 12. 内嵌预览通道（关键可行性依据）

### 通道 A：MCP image 内容块（主）

`@deepseek-ai/dsh-mcp-client` 支持 MCP 的 `image` 内容块：
- 只接受 `image/png|jpeg|webp|gif`
- 经 `attachments.saveImages` 持久化，并以 `{type:"image", attachment}` 进入消息内容，由前端 `renderMessageImages` 在对话内渲染
- `image/gif` 不进入归一化路径（`needsNormalization` 对 GIF 返回 false），**动画帧不被压平**
- 前提：当前模型声明了 `image` 输入能力。已确认默认模型 `deepseek-official/deepseek-flash` 的 `inputModalities` 为 `["text","image"]`
- 本 GUI 已实测：工具结果中的图片块正常内嵌显示

### 通道 B：回复内 Markdown 绝对路径（兜底）

前端 `localPathMediaUrl` 会把**以 `/` 开头的 Markdown 图片目标**映射为 `${origin}/api/file?path=<encodeURIComponent(目标)>`。

Host 侧 `/api/file` 接收入参后用 `path.resolve(cwd, p)`，而 Node 的 `win32.normalize` 会把形如 `/D:/x/y.gif` 的路径正确识别出驱动器号 `D:` 并归一化为 `D:\x\y.gif`。因此：

```markdown
![anim](/D:/myprogram/dshplugin/renders/<runId>/out/Equation.gif)
```

会被解析为 `http://127.0.0.1:3080/api/file?path=%2FD%3A%2F...`，同源请求携带既有登录态，图片正常显示。**这条路与模型是否具备图片能力无关**，因此是可靠的兜底。

信封里的 `previewMarkdown` 就是按这个格式生成的，模型只需原样粘贴。

> 由此产生的硬约束：产物路径不能含空格、括号、中文——已在 7.1 节通过 run 命名规则保证。

---

## 13. 安装与接入

### 13.1 `install.ps1`

1. **依赖体检**：检查 python / manim / ffmpeg / latex，任一缺失则给出明确的安装指引后中止。
2. **探测绝对路径**：解析出 python.exe、manim、ffmpeg.exe 的绝对路径。
3. **备份**：`~/.dsh/profiles/web/cordis.patch.yml` → `cordis.patch.yml.bak-<yyyyMMddHHmmss>`。
4. **幂等挂载**：若已存在 `id: mcp-manim` 则先移除旧块再插入，最终追加：

```yaml
# manim MCP — Manim 可视化解释插件（D:\myprogram\dshplugin）
- insert:
    - id: mcp-manim
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: manim
        transport: stdio
        command: '<python 绝对路径>'
        args: ['D:\myprogram\dshplugin\manim-mcp\server.py']
        failOnStartupError: true
        env:
          MANIM_MCP_PYTHON: '<python 绝对路径>'
          MANIM_MCP_MANIM: '<manim 绝对路径>'
          MANIM_MCP_FFMPEG: '<ffmpeg 绝对路径>'
          MANIM_MCP_RENDER_ROOT: 'D:\myprogram\dshplugin\renders'
```

> `env` 必须显式传入：`dsh-mcp-client` 会给子进程一个**清洗过**的环境（凭据形状与陈旧 `DSH_*` 变量被丢弃），不显式传会有 PATH 风险。

5. **安装 Skill**：复制 `skills\manim-explainer` → `~/.dsh/skills\manim-explainer`（已存在则先备份）。
6. **自检**：运行 `python manim-mcp\server.py --selftest`，做一次真实的小场景渲染并打印产物路径。
7. **提示重启**：明确告知需要重启 dsh web 才生效。

### 13.2 `uninstall.ps1`

- 按 `id: mcp-manim` **精确删除**该 insert 块（用 YAML 解析，不靠字符串匹配），保留其它配置与注释。
- 删除 `~/.dsh/skills\manim-explainer` 副本。
- `renders\` 默认保留，加 `-PurgeRenders` 才删除。
- **绝不触碰 shipped preset 与任何部署自带目录。**

---

## 14. 配置项

全部可通过 `env` 覆盖，均有安全默认值：

| 变量 | 默认 | 说明 |
|---|---|---|
| `MANIM_MCP_PYTHON` | `sys.executable` | 用于 `-m manim` 的解释器 |
| `MANIM_MCP_MANIM` | 自动探测 | manim 可执行文件，设了就优先用 |
| `MANIM_MCP_FFMPEG` | PATH 上的 `ffmpeg` | ffmpeg 可执行文件 |
| `MANIM_MCP_RENDER_ROOT` | `<repo>\renders` | 产物根目录 |
| `MANIM_MCP_MAX_CONCURRENCY` | `1` | 并发渲染数 |
| `MANIM_MCP_TIMEOUT_SEC` | `180` | 单次渲染超时 |
| `MANIM_MCP_GIF_TARGET_BYTES` | `8388608`（8MB） | GIF 目标体积 |
| `MANIM_MCP_GIF_MAX_BYTES` | `18874368`（18MB） | GIF 硬上限，超则降级 |
| `MANIM_MCP_KEEP_RUNS` | `50` | 保留的 run 数量 |
| `MANIM_MCP_LOG_LEVEL` | `INFO` | 日志级别（写 stderr，不污染 stdout 的 MCP 帧） |

> MCP stdio 的 stdout 是协议通道，**任何日志只能走 stderr**。

---

## 15. 错误处理与降级总表

| 场景 | 行为 |
|---|---|
| `check` 发现语法/结构错误 | 不渲染，直接返回 `stage: "validate"` 与问题清单 |
| Manim 渲染失败 | 返回 `stage: "manim"` + 解析后的行号与 hint |
| 渲染超时 | 杀进程树，返回 `stage: "timeout"` 与部分 stderr |
| GIF 体积超硬上限且降级穷尽 | 改用 WebP；再不行只给 PNG 海报，`warnings` 说明 |
| ffmpeg 不可用 | 仍返回 MP4，`preview` 指向 PNG 海报，`warnings` 说明 |
| 中文字体缺失 | 回退 `sans-serif` 并 `warnings` 提示可能显示为方框 |
| 产物目录不可写 | 返回明确错误，提示检查 `MANIM_MCP_RENDER_ROOT` 权限 |
| MCP 服务启动即失败 | `failOnStartupError: true` 让 DSH 在重启时立刻报错，而不是静默无工具 |

---

## 16. 测试策略

### 16.1 单元测试（`pytest`，不依赖真实渲染）

- `test_diagnostics.py`：喂入真实 stderr 样本（含 traceback、ANSI、进度条噪声），断言解析出的类型/行号/hint。
- `test_postprocess.py`：mock ffmpeg，断言降级链依次尝试 fps/宽度的组合，且在硬上限处正确切到 WebP、再切到 PNG。
- `test_workspace.py`：runId 命名合法（无空格/括号/中文）、保留策略按时间正确删除、run.json 往返一致。
- `test_scenes.py`：4 个模板对给定入参生成的代码能被 `ast.parse`，且包含必需结构；对非法入参给出可读错误。

### 16.2 端到端测试

- `python manim-mcp\server.py --selftest`：真实渲染一个「中文标题 + LaTeX 公式 + 图形」的场景，断言 MP4/GIF 产出、GIF < 18MB、`previewMarkdown` 路径存在且文件可读。
- 渲染耗时打印，作为性能回归基线（热态应 ≤ 20 秒）。

### 16.3 浏览器验收（必须做）

1. 重启 dsh web。
2. 新开对话，问一个「值得画」的问题（例如「为什么 e^{iπ}+1=0」）。
3. 断言：动画**内嵌显示**在对话里、可动、路径与 `previewMarkdown` 一致。
4. 断言：Disable 掉 image 通道（切换到纯文本模型）后，通道 B 的 Markdown 仍能显示。

---

## 17. 验收标准

1. `install.ps1` 在干净环境一次跑通，重启后 `mcp__manim__*` 工具出现在工具列表中。
2. 4 个高层工具各自能产出正确动画（人工看一遍 4 段产物）。
3. 含中文与公式的场景渲染正确，无方框、无乱码。
4. 故意给一段有错的 Manim 代码，返回的信封含正确行号与可执行 hint。
5. 单个动画端到端 ≤ 20 秒（draft，热态）。
6. 对话内动画正常内嵌显示。
7. `uninstall.ps1` 跑完后 `cordis.patch.yml` 与安装前**逐字节等价**（除备份文件外）。
8. `pytest` 全绿。

---

## 18. 风险与未决项

| 风险 | 影响 | 缓解 |
|---|---|---|
| 主动触发让每轮回答多 10–14 秒 | 交互变慢 | 默认 draft 画质；一轮最多 1 张；`check` 挡掉低级错误；正文不阻塞在渲染上 |
| 模型写的 Manim 代码质量不稳定 | 动画不达预期 | 高层模板承担 80% 场景；`style_guide` 给精确常量；自愈协议兜底 |
| 首次渲染 35 秒（LaTeX 冷启） | 首次体验明显慢 | SKILL.md 说明；`install.ps1` 的自检预热 MiKTeX 格式 |
| 复杂场景渲染时间不可控 | 超时 | 180 秒超时 + 模板本身限制复杂度（单想法原则） |
| MiKTeX 在某些沙箱策略下无法写自身日志 | LaTeX 全挂 | MCP 由 DSH Host 直接拉起，不受工具沙箱限制；已在 full-access 下实测通过 |
| MCP 工具数量占用上下文 | 略增提示成本 | 工具名精简、描述精炼；重的风格内容放 Skill 而非工具描述 |

### 未决项

无。所有设计决策已在上文明确。

---

## 19. v2 预留（不在本次范围）

- DSH Client 插件：把动画渲染成带播放控制的工具卡片（可暂停、逐帧、全屏）。
- 动画序列：一次回答产出多幕连贯动画。
- 交互式参数：用户拖动滑块改变参数并重渲染。
- 缓存层：相同场景代码命中缓存直接复用 MP4。
