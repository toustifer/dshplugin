# manim-mcp（组件 1）

把「公式推导 / 函数图像 / 流程结构 / 左右对照 / 任意 Manim 代码」渲染成 MP4，并自动产出 GIF/WebP/PNG 预览与结构化诊断的 stdio MCP 服务。

本组件是 `dsh-manim` 项目的一部分，项目总览见 [`..\README.md`](../README.md)；设计依据见
[`..\docs\superpowers\specs\2026-09-12-manim-visual-explainer-design.md`](../docs/superpowers/specs/2026-09-12-manim-visual-explainer-design.md)。

---

## 1. 依赖与验证

| 依赖 | 用途 | 版本（实测） | 验证命令 |
|---|---|---|---|
| Python | 运行服务器与 Manim | 3.13.5 | `D:\ProgramData\anaconda3\python.exe -V` |
| Manim Community | 渲染引擎 | 0.20.1 | `D:\ProgramData\anaconda3\python.exe -m manim --version` |
| MiKTeX（LaTeX） | `MathTex` 公式排版 | 本机已预热 | `latex --version` |
| ffmpeg | 时长得探测、GIF/WebP/PNG 后处理 | `D:\tools\system_cmd\ffmpeg.EXE` | `ffmpeg -version` |

缺 LaTeX 时公式会失败、缺 ffmpeg 时只剩 mp4 没有预览图。三者都能用一条命令验完：

```powershell
D:\ProgramData\anaconda3\python.exe manim-mcp\server.py --selftest
```

---

## 2. 8 个工具

模型侧看到的完整名为 `mcp__manim__<rawName>`。raw name 固定为下列 8 个，不接受别名。

| raw name | 一句话用途 | 必需参数 |
|---|---|---|
| `equation` | 多步 LaTeX 逐步变形，展示公式推导（3b1b 式） | `steps`（2–6 个 LaTeX 字符串） |
| `graph` | 函数图像，可叠加切点/切线、面积填充、参数滑动 | `expressions`（1–3 个 "x**2" 形式的表达式） |
| `diagram` | 流程 / 架构 / 因果框图 | `nodes`、`edges` |
| `compare` | 左右对照，突出两种做法或概念的差异 | `left`、`right` |
| `render` | 逃生口：渲染任意完整 Manim 代码 | `code`（含 `from manim import *` 与 Scene 子类） |
| `check` | 0.1 秒静态体检：语法、import、Scene 子类；不渲染 | `code` |
| `style_guide` | 取本机精确风格常量、可用中文字体、模板参数、可用骨架 | 无 |
| `runs` | 查看历史渲染；`action=get` 取回某次生成的完整 `scene.py` | `action`（`list` / `get`） |

所有工具都是**同步语义**：内部 `await` 子进程，调用返回时结果已就绪，不会返回「稍后再说」。
返回值统一是「文本信封 + 图片内容块」：第一块是 JSON（`ok`、`runId`、诊断、警告、产物路径），
第二块在成功且有预览图时是 GIF/PNG 图片本体。

写原始 Manim 代码前先调 `check`，不要用一次 10 秒的渲染去发现一个语法错误。

---

## 3. 配置项

全部通过 `MANIM_MCP_*` 环境变量覆盖。DSH 的 MCP 行交给子进程的是**被擦洗过的环境**，因此
需要固定值的场合应显式传入，而不是依赖 PATH 探测。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MANIM_MCP_PYTHON` | `sys.executable` | 用于 `-m manim` 的解释器 |
| `MANIM_MCP_MANIM` | 自动探测 | manim 可执行文件，设了就优先用 |
| `MANIM_MCP_FFMPEG` | PATH 上的 `ffmpeg` | ffmpeg 可执行文件 |
| `MANIM_MCP_RENDER_ROOT` | `<repo>\renders` | 产物根目录 |
| `MANIM_MCP_MAX_CONCURRENCY` | `1` | 并发渲染数 |
| `MANIM_MCP_TIMEOUT_SEC` | `180` | 单次渲染超时（秒） |
| `MANIM_MCP_GIF_TARGET_BYTES` | `8388608`（8MB） | GIF 目标体积 |
| `MANIM_MCP_GIF_MAX_BYTES` | `18874368`（18MB） | GIF 硬上限，超则降级 |
| `MANIM_MCP_KEEP_RUNS` | `50` | 保留的 run 数量；`0` 表示不清理（动画库会一直累积） |
| `MANIM_MCP_LOG_LEVEL` | `INFO` | 日志级别（写 stderr，**不污染 stdout 的 MCP 帧**） |

`MANIM_MCP_GIF_TARGET_BYTES` 大于 `MANIM_MCP_GIF_MAX_BYTES` 会在启动时报配置错误并以退出码 2 结束。

---

## 4. `--selftest`

```powershell
$env:MANIM_MCP_RENDER_ROOT="D:\myprogram\dshplugin\renders"
D:\ProgramData\anaconda3\python.exe manim-mcp\server.py --selftest
```

真机渲染一个样例场景（中文文字 + `MathTex` 公式 + 圆形），然后生成预览图并打印路径。

| 退出码 | 含义 |
|---|---|
| `0` | 全链路健康：渲染成功、预览生成成功 |
| `1` | 渲染本身失败（LaTeX 缺包、Manim 异常、超时等），诊断已打印 |
| `2` | 依赖缺失或渲染目录不可用（缺 ffmpeg / Python，或 `MANIM_MCP_RENDER_ROOT` 不可写） |

依赖检查在**创建任何目录之前**执行：缺 ffmpeg 时退出码 2 且不会在动画库里留下半个 run。

---

## 5. 排错

1. **先读信封里的 `hint`，再看 `line` / `sourceLine`。** 诊断层把 manim 的 traceback 解析成结构化诊断，
   `line` 与 `sourceLine` 指向你自己代码里出问题的那一行，`hint` 是可直接照做的修复建议。
   常见坑映射见 Spec §9.2。注意 manim 默认把 traceback 画在 rich 边框面板里（还会把长路径折成两行），
   诊断层会先把面板还原成普通文本再解析——改动这段解析后**必须**跑一次真实的失败渲染验证，
   手写的 fixture 无法覆盖这个格式。
2. **MiKTeX 首次编译很慢。** 第一次用到某个宏包时会现装现编，可能超过默认 180 秒超时。
   再跑一次通常就过了；长期方案是预先 `mpm --update-db` 并预热常用宏包。
3. **不要依赖 PATH。** 若 `MANIM_MCP_MANIM` / `MANIM_MCP_FFMPEG` 指向的可执行文件被移动或删除，
   渲染仍会以结构化诊断失败（不会抛异常），修复方式是重跑 `install.ps1` 重新探测绝对路径，
   或显式设置 `MANIM_MCP_*` 覆盖。
4. **中文显示成方框。** `style_guide` 返回的 `cjkFont` 为 `null`，说明本机没探测到中文字体；
   装 `Microsoft YaHei` 或 `SimHei` 即可。
5. **stdout 必须干净。** MCP 的握手帧走 stdout，任何 banner 或日志误写到 stdout 都会让
   `list_tools` 直接失败。改动 `app.py` / `server.py` 后跑一次 `tests\manual\stdio_smoke.py` 验这条通路。

---

## 6. `renders\` 布局与 `index.json`

```
renders\
  index.json        动画库面板（Plan 2）的数据源
  <runId>\
    scene.py        生成或模型提供的代码（可复现、可再编辑 —— `runs` 工具就是读它）
    media\          manim 中间产物（partial movie files 等）
    out\            最终产物 mp4 / gif / webp / png
    run.json        元数据：工具、参数、耗时、产物、警告
```

- `runId` 形如 `YYYYMMDD-HHMMSS-<8位hex>`（32 位熵），按字符串排序即按时间排序。
- 目录名与文件名**只含 ASCII 字母数字与 `-`**：空格、括号、中文会破坏 Markdown 图片语法与命令行引号处理。
- `index.json` 在每次渲染**成功或失败**后增量更新，顶层是 `{version, updatedAt, runs: [...]}`。
  面板只读它，不扫描目录。

---

## 7. 开发

```powershell
cd D:\myprogram\dshplugin
D:\ProgramData\anaconda3\python.exe -m pytest                  # 单元测试，不需要真机渲染
D:\ProgramData\anaconda3\python.exe tests\manual\render_templates.py   # 四个模板各渲染一次（真机）
D:\ProgramData\anaconda3\python.exe tests\manual\acceptance_tools.py   # 经真实 stdio 服务端调用四个工具
D:\ProgramData\anaconda3\python.exe tests\manual\stdio_smoke.py        # 子进程 + stdio 冒烟
```

**改动 `manim_mcp\scenes\` 之后必须跑 `render_templates.py`。** 单元测试只能断言生成的源码文本，
而「`ast.parse` 通过但 import 时 `NameError`」这类缺陷只有真机渲染能发现。

**改动 `tools\`、`app.py`、`engine\render.py` 或 `engine\postprocess.py` 之后必须跑 `acceptance_tools.py`。**
`render_templates.py` 直接调 `scenes.build` 并自己起子进程，完全绕开 pipeline，因此它发现不了工具层的问题。
这条命令存在的理由很具体：外部程序（manim / ffmpeg）**必须**以 `stdin=DEVNULL` 启动。服务端的 stdin 是
客户端持有的、整场会话都不关闭的 JSON-RPC 管道；一旦子进程继承了它，子进程读到 stdin 就会永久阻塞。
这个缺陷只在「stdio 服务端 + 工具调用」这一种组合下复现——直接调用、in-process 客户端、`asyncio.to_thread`
**全都正常**，所以只有走真实 stdio 的验收能拦住它。
