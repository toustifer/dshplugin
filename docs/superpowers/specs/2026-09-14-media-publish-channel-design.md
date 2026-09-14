# DSH 通用文件发布通道 — 设计方案

- 日期：2026-09-14
- 项目根目录：`D:\myprogram\dshplugin`
- 状态：待用户评审
- 关系：这是 `2026-09-12-manim-visual-explainer-design.md` 的**后续独立特性**。Manim 那条线解决「把动画画出来」，本方案解决「把产物交给用户看」。两者共用同一条同源取字节通道，但代码不互相依赖。

---

## 1. 背景与目标

Manim 那条线只解决了图片：动画的 GIF 能内嵌进回答正文，因为前端原生渲染 Markdown 图片。一旦产物是**视频、音频、PDF、或者任意文件**，就没有任何通道能把它送进对话——用户只能自己去磁盘上找。

目标：给模型一个**通用的「发布文件」能力**，把任意本地文件以合适的形态呈现给用户，用户不需要做任何额外操作。

成功的样子：模型产出了一份 12 秒的带旁白讲解视频和一份 PDF 报告，它调用一次发布工具，回答里就出现一个能直接播放的视频和一个能直接翻看的 PDF。

### 1.1 判据

1. 视频能在对话流里**直接播放**（不是下载链接）。
2. 音频能直接播放，PDF 能直接翻看（若 CSP 实测不允许则退化为一次点击在右侧栏翻看，并在规格里写明）。
3. 任意其它格式至少给出**文件名 + 类型 + 大小 + 可打开**。
4. 发布失败时（超限、越界、不存在）**给出可读的原因**，绝不发出一个注定 404 或 413 的引用。
5. 不改动、不覆盖任何 shipped UI。
6. 不破坏已验收的 Manim 那条线。

---

## 2. 已实测的环境事实（非推断）

以下每一条都是在本机读 shipped 源码或 Inspect 查到的，不是推测。

| 事实 | 证据 |
|---|---|
| MCP 工具的 wire name 是 `mcp__<serverName>__<rawName>` | `dsh-mcp-client/lib/index.js:121` `publicToolName()` |
| MCP `image` 块**只收 PNG/JPEG/WebP/GIF**，其它 MIME 直接 throw | `dsh-mcp-client:307` `throw new Error("the declared media type is not PNG, JPEG, WebP, or GIF")` |
| MCP `audio` 块被降级成占位文本 | `dsh-mcp-client:439` `[audio result unsupported: ...]` |
| MCP `resource` 块被降级成占位文本 | `dsh-mcp-client:442` `[embedded resource unsupported...]` |
| MCP `resource_link` 被降级成一行文本 | `dsh-mcp-client:436` |
| 核心内容块词汇里**本来就有通用的 `file` 块** | `dsh-llm/lib/types/types.d.ts:72` 附近 `FileBlock { type:'file'; attachment: FileAttachmentRef }` |
| 但 MCP 这条路**产出不了** `file` 块 | `dsh-mcp-client` 的 `projectContent` 只有 `case "text"/"image"/"resource_link"/"audio"/"resource"`（`:427–441`），**没有 `file`**；附件库 239 个对象实测只有 PNG/JPEG/WebP |
| `tool.call.toolview` 按**工具名**分发，key 域开放 | Inspect `Slots.listSubTree`：`keyDomain: "open: any string the owner dispatches"`，已占用列表里**没有** `mcp__*` |
| 占用未注册的 key 对自家工具是**纯增量** | 同上 catalog：*"an unclaimed key falls back to the generic tool row, so registering is additive for your own tool"* |
| 卡片能拿到**已完成的工具结果** | `dsh-client-ui-conversation/lib/types/client/contract/records.d.ts:151` `ToolResultNode.content: readonly ContentBlock[]`；`ToolCallBlock = RunningToolCall \| ToolResultNode` |
| 区分「进行中」与「已完成」只能靠 `kind` 是否存在 | 同上 `:251` `RunningToolCall` **没有 `kind` 字段**；只有 `ToolResultNode` 有 `kind: 'tool-result'` |
| 想改助手正文必须替换 `assistant-step` | Inspect：`conversation.chat.node` 的 `assistant-step` 已占用，`replaceRisk: shadows-shipped-ui` |
| 消息图片槽位拿不到正文文本 | Inspect：`conversation.message.images` 是 `single` 型，ownerProps 只有 `images`/`loadImage`/`align`/`compact` |
| `/api/file` 支持 audio/video 响应，且**不限制 MIME** | `dsh-api-session-controller` README 原文 |
| `/api/file` 对**所有**文件套用同一个体积上限 | 同上：*"All files use `ctx.attachments.imageLimits.maxImageBytes` (normally 20 MiB); exceeding this limit returns 413"* |
| 同源引用形式 = **去掉盘符的绝对路径**，且 `fs` 的 cwd 必须与产物同盘 | 见 2026-09-12 规格第 12 节通道 B；已用真实 cookie 对运行中的 Host 实测 200 |
| `/api/file` 的响应带**最严格的 sandbox CSP** | 实测响应头 `content-security-policy: sandbox; default-src 'none'`（见 §9.1） |
| `pdftoppm` / `pdftocairo` 随 MiKTeX 自带，**不需要新依赖** | `Get-Command pdftoppm` → `…\MiKTeX\miktex\bin\x64\pdftoppm.exe` |
| 右侧栏能预览 PDF（内置 pdf.js） | `dsh-client-ui-sidebar-documentpreview/lib/client.js:26708` `extensions: ["pdf"]` |
| 我们的 JSON 信封在会话记录里**逐字节保留** | `tests/manual/envelope_survives.mjs`：742 条 tool/result 中 `re-dump matches recorded text: true`（见 §9.2） |

---

## 3. 为什么只能这样做

三条看起来更省事的路，实测下来都是堵死的：

1. **让 MCP 直接返回 video/audio/resource 内容块** —— 客户端会把它们降级成占位文本（见 §2）。这条路不是"没试"，是 shipped 代码明确这么写的。
2. **在助手正文里用 Markdown 标记，让插件替换渲染** —— 助手正文由 `assistant-step` 渲染，槽位已被占用且 `replaceRisk: shadows-shipped-ui`；替换它意味着**整段正文的 Markdown（表格、代码块、链接、公式）都由我们重写**。代价与风险都不成比例。
3. **用 `conversation.message.images` 槽位接管** —— 它是 `single` 型且只收到这条消息的**图片引用**，拿不到正文文本，因此无法"读到标记再渲染播放器"。接管还会覆盖 shipped 的图片呈现。

剩下唯一一条既是官方扩展点、又不覆盖任何 shipped UI 的路：**给自家工具注册 `tool.call.toolview`**。

它的位置是**工具卡片**（对话流里，工具调用处），不是助手文字段落中间。这一点用户已明确接受。**和图片的体验一致**：工具返回描述符，界面自动渲染，用户什么都不用做。

### 3.1 官方既有的交付通道，以及本方案补的是哪一块

DSH 早就有「把文件交给用户」的正式通道，本方案**不重复它、也不接管它**：

| 官方件 | 作用 |
|---|---|
| `dsh-tool-present`（工具名 `present`） | 声明"这些文件是交付物" |
| `dsh-client-ui-deliverables` | 它的 UI：注册 `tool.call.toolview` key **`present`**（已被占用）与 `conversation.chat.turnTail`——**每轮结束的「产物行」** |

两条关键事实：

1. **产物行的词汇来自 mutation 工具的 `locations` 元数据**，不靠模型记得说。也就是说 `write`/`edit` 产出的文件**自动**会被列出来。
2. **每个 chip 的打开方式是"右侧栏的文本预览 tab"**（README 原文：*"opens the file through the owner's `openFile`, which the chat view routes to the right Sidebar as a text-preview tab"*）。

**所以缺口是真实且官方未覆盖的**：DSH 能*列出*产物、能以文本预览打开，但**不能播放视频、不能翻 PDF、不能播音频**。本方案补的正是这一段——内嵌播放，而不是又一个"列出 + 打开"。

因此：**不注册 `present` 的 key**（已被占用，接管它等于破坏官方交付物体验），也不去动 `conversation.chat.turnTail` 的产物行。

### 3.2 行为引导放在哪：工具描述，不配 skill

这是实测出来的官方做法，本方案照做。

| 能力 | 行为引导写在哪 | 有 skill 吗 |
|---|---|---|
| 发图片（`read_image`） | 工具自己的 `description` | **没有** |
| 交付文件（`present`） | 工具自己的 `description`（`dsh-tool-present/lib/index.js:25`，即"you must call present after writing it and before your final response"那段） | **没有** |
| 画动画（本项目的 `manim-explainer`） | skill | 有（这是**本项目**加的，不是官方做法） |

证据：`dsh-tool-present` 整个包里 `prompt` / `skill` / `systemPrompt` / `instructions` **零命中**；两个 skills 目录里也没有任何讲附件的 skill。

**为什么这里不该用 skill**：skill 要靠路由器匹配才会被加载，而**加载失败正是我们最怕的那个失败模式**——模型做了视频却忘了发布。工具描述则**永远在上下文里**。官方把这段引导放进工具描述而不是 skill，正是这个道理。

所以 `publish_file` 的 `description` 必须自己承载全部行为规范：什么时候发、什么时候不发、一轮最多发几个、什么格式不值得发。这一条是硬要求，不是"最好有"。

> 注：本项目已有的 `manim-explainer` skill 保持不动。它管的是"什么时候画"，与"什么时候发布"是两件事，各自独立。

---

## 4. 架构

两个新组件，各自单一职责，通过一个 JSON 契约通信。

| 组件 | 形态 | 职责 | 依赖 |
|---|---|---|---|
| **`media-mcp/`** | Python stdio MCP | 一个工具 `publish_file(path, title?)`：校验路径 → 嗅探 MIME → 分类 kind → 算出同源引用 → 返回描述符 | **仅 Python 标准库**，不 import manim,不 import ffmpeg |
| **`dsh-media-view/`** | 手写打包 client 插件 | 注册 `tool.call.toolview`（key = `mcp__media__publish_file`），从工具结果里解析描述符，按 kind 渲染 | `react`（由 module loader 提供）、`sidebarRight`（仅供 PDF/其它格式的"在右侧栏打开"退化路径） |

为什么 client 端不并进 `dsh-manim-gallery`：那个插件是 **manim 专属**的（读 `renders/index.json` 的 run 列表）。通用渲染器和它没有共同数据模型，合在一起会让两边都难改、测试也互相牵制。分开后失败域独立：渲染器坏了不影响动画库，反之亦然。

为什么 MCP 不并进 `manim-mcp`：`manim-mcp` 的 serverName 是 `manim`，工具会叫 `mcp__manim__publish_file`——把通用能力挂在 manim 命名空间下，语义上就错了，而且它会让一个只需要标准库的操作为了启动而付出 manim 环境的加载成本。

---

## 5. 数据流与契约

```
模型调用 mcp__media__publish_file
   │
   ├─► MCP 校验：存在？是普通文件？在允许根内？与 fs 同盘？≤ 上限？
   │      任一条不过 → 返回 { ok:false, reason, detail }（可读原因，不发引用）
   │
   └─► 通过 → 返回文本信封
            { "ok": true,
              "media": { "kind": "video", "path": "D:\\...\\x.mp4",
                         "reference": "/myprogram/dshplugin/out/x.mp4",
                         "name": "x.mp4", "mime": "video/mp4",
                         "bytes": 1234567, "title": "…" } }
                    │
                    ▼
        client 插件从 ToolResultNode.content 里取 text 块 → JSON.parse
                    │
                    ▼
        按 kind 渲染，src = /api/file?path=<reference 的 encodeURIComponent>
```

**`reference` 由 MCP 算好**，与 Manim 那条线的 `previewMarkdown` 使用**同一套规则**（去掉盘符的完整绝对路径）。client 端不做任何路径推理，只做 URL 编码——把"路径怎么解析"这件事收敛在一处，是前两次 404 换来的教训。

---

## 6. `publish_file` 工具规格

签名：`publish_file(path: string, title?: string)`

### 6.1 校验顺序与失败原因（全部结构化，且都能被模型读到并据此纠正）

| 检查 | 不过时的 `reason` | 给模型的提示 |
|---|---|---|
| 路径非空、绝对 | `not-absolute` | 要求绝对路径 |
| 存在 | `missing` | 文件不存在 |
| 是普通文件 | `not-a-file` | 是目录或特殊文件 |
| 在允许根内 | `outside-root` | 列出允许根 |
| 与 `fs` cwd 同盘 | `wrong-drive` | 说明引用形式不带盘符，必须同盘 |
| `bytes ≤ maxBytes` | `too-large` | 给出上限与实际大小 |

`maxBytes` 默认 **20 MiB**（与 shipped `/api/file` 的上限一致），可用环境变量覆盖。**超出时拒绝，不返回引用**——因为那个引用注定 413，让前端去撞墙等于把失败留给用户。

### 6.2 MIME 嗅探

先按扩展名查表，再用**magic bytes** 复核（PNG/JPEG/GIF/WebP/PDF/MP4-family(`ftyp`)/WAV/MP3/FLAC/OGG）。两者冲突时以 magic 为准，并在信封里带一个 `warnings` 说明。扩展名伪装是真实存在的（把 .exe 改名 .mp4），而渲染器要按 kind 决定用 `<video>` 还是 `<iframe>`，猜错会触发浏览器解析异常。

### 6.3 kind 分类

`image` / `video` / `audio` / `pdf` / `text` / `other`。分类只用于**选渲染器**，不用于限制访问。

### 6.4 配置

| 环境变量 | 含义 | 默认 |
|---|---|---|
| `MEDIA_MCP_ROOTS` | 允许发布的根目录（`;` 分隔） | 仓库根目录 |
| `MEDIA_MCP_MAX_BYTES` | 体积上限 | `20971520`（20 MiB） |
| `MEDIA_MCP_FS_CWD` | `fs-sandbox.cwd` 的路径，用来校验同盘 | 仓库根目录 |
| `MEDIA_MCP_PDF_PAGES` | PDF 首页预览最多转几页 | `3` |
| `MEDIA_MCP_PDF_DPI` | 光栅化 DPI | `110` |
| `MEDIA_MCP_PDFTOPPM` | `pdftoppm` 可执行文件 | 随 MiKTeX 的那个 |

`MEDIA_MCP_FS_CWD` 必须是**安装脚本写入的那个值**，不允许各写各的——两处不一致就是"引用永远 404"这类故障的温床。

### 6.5 PDF 光栅化

`kind == "pdf"` 时，MCP 额外做一步：用 `pdftoppm -png -r <dpi> -f 1 -l <pages>` 把前若干页转成 PNG，写到 `<render root>/_pdf/<sha1 前 12 位>/page-01.png`，并把它们作为**额外的 image 媒体描述符**放进信封。

- 页数上限 **3**（`MEDIA_MCP_PDF_PAGES`，见 §6.4）
- DPI 默认 **110**（够看清正文，单页约 100–200 KB，远离 20 MiB 上限）
- 目录用**内容哈希**命名：同一份 PDF 重复发布不会反复转换，也不会因文件名碰撞互相覆盖
- 转换失败（PDF 损坏、`pdftoppm` 缺失）**不让整次发布失败**：信封仍返回 PDF 本身与右侧栏按钮，另在 `warnings` 里说明"首页预览不可用"
- 总页数写进 `media.pages`，卡片据此显示"共 N 页，显示前 3 页"

### 6.6 工具描述就是行为层（硬要求）

按 §3.2 的实测结论，**不配 skill**，全部行为规范由 `publish_file` 的 `description` 承载。它必须明确回答四件事：

1. **什么时候该发**：产出的是用户要「看/听/读」的东西（视频、音频、PDF、图片、报告），且用文字描述不如直接给。
2. **什么时候不该发**：中间产物、日志、调试截图；用户没要看的；一句话就能说清的东西；同一份文件重复发。
3. **一轮最多发几个**：定 **3 个**。再多就变成刷屏，重点被淹没——与 `manim-explainer`「一轮最多 1 个动画」同源的理由。
4. **超限怎么办**：明说 20 MiB 上限，超了要么先压缩/切片，要么把路径以文字给出并说明原因，**不要反复重试**。

描述是模型唯一会读到的规范，写含糊等于没有。它也要说清失败时会返回 `reason`，模型据此纠正而不是盲目重试。

---

## 7. 渲染器规格（`dsh-media-view`）

### 7.1 注册

```js
exports.inject = ["slots", "sidebarRight"];
ctx.slots.inject("tool.call.toolview", () =>
  ctx.slots.register({ name: "tool.call.toolview", key: "mcp__media__publish_file" }, MediaView)
);
```

key 必须是 **`mcp__media__publish_file`** 这个字面量。契约明确写着 *"a typo simply never renders"*——打错不会报错、不会降级提示，只是永远不出现在界面上。因此有一条测试**逐字**断言这个 key。

### 7.2 状态机

组件收到的 `block` 是 `RunningToolCall | ToolResultNode`。判据只有一条：**`kind` 字段存在与否**——`RunningToolCall` 没有 `kind`，只有 `ToolResultNode` 有 `kind: 'tool-result'`。因此**不能**用 `block.kind === 'tool-call'` 之类的猜测去判进行中，那永远为假。

| 状态 | 判据 | 界面 |
|---|---|---|
| 进行中 | `block.kind !== "tool-result"`（含 `kind` 缺失） | 骨架/加载态，**不渲染空播放器** |
| 失败 | `isError === true` 或信封 `ok === false` | 显示 `reason` 的可读中文说明 |
| 成功 | 解析出 `media` | 按 kind 渲染 |

### 7.3 各 kind 的渲染

| kind | 元素 | 备注 |
|---|---|---|
| `image` | `<img>` | |
| `video` | `<video controls preload="metadata">` | 不自动播放 |
| `audio` | `<audio controls>` | |
| `pdf` | **光栅化后走图片通道**：MCP 用 `pdftoppm` 把前 ≤3 页转成 PNG，按 `image` 渲染；卡片另给"翻看完整 PDF"按钮 | 见 §9.1：`<iframe>` 被 shipped 的 sandbox CSP 判死，这是实测后的替代方案 |
| `text` | `<pre>` 前 **40 行** + 总行数；末尾注明"已截断" | 40 是一个屏幕放得下又不至于只剩两行的数 |
| `other` | 图标 + 文件名 + 大小 + 打开/下载 | |

`src` 一律为 `/api/file?path=<encodeURIComponent(reference)>`。

"在右侧栏打开"复用已验收的写法：`sidebarRight.openResource("dsh-resource://file/absolute/" + …)`，并对"座位未挂载时抛异常"做同样的重试与告警处理。

### 7.4 视觉

只用 `--dsw-*` 主题 token，不硬编码颜色（沿用 Manim 面板的红线）。播放器尺寸随卡片宽度，视频保持 16:9。

---

## 8. 错误与边界：不允许静默失败

这是本方案里最容易被做坏的部分，逐条钉死：

1. **信封 JSON 解析失败** → 退化为渲染一个普通说明行，**绝不抛异常**。抛出去会把整个对话渲染带崩，一个格式化失误就毁掉整屏。
2. **`media` 字段缺失或形状不对** → 同上。
3. **超限 / 越界 / 不存在** → MCP 在源头拒绝（§6.1），前端只需展示 `reason`。
4. **引用取不到（404）** → `<video>`/`<audio>` 的 `onError` 必须显示"文件已不存在"，而不是留一个黑洞。
5. **座位未挂载** → 右侧栏按钮的既有重试 + 明确 warn。
6. **key 打错** → 测试逐字断言（§7.1）。

---

## 9. 两个曾列为未知、现已实测的结论

设计初稿把两条留作"实现前先测"。它们已在 2026-09-14 实测完毕，**不再是未知项**，下面写的是结论与证据。

### 9.1 PDF 不能内嵌 `<iframe>`，改用光栅化

对真实文件发 `HEAD /api/file`，响应头是：

```
content-type: application/pdf
content-security-policy: sandbox; default-src 'none'
cache-control: private, no-store
x-content-type-options: nosniff
```

`sandbox` **不带任何 `allow-*` 令牌**，等于施加全部沙箱限制：唯一源、禁脚本、禁插件。浏览器内置 PDF 阅读器在这种 frame 里不会渲染，因此 `<iframe src="/api/file?...">` 这条路判死。

替代方案（已确认工具存在，无需新依赖）：

| 工具 | 位置 | 备注 |
|---|---|---|
| `pdftoppm` / `pdftocairo` | `…\MiKTeX\miktex\bin\x64\` | **MiKTeX 自带**，而 MiKTeX 是本项目既有依赖（Manim 的 LaTeX 需要） |
| Python `fitz` / `pdf2image` / `PIL` | 本机已装 | 备用，但会新增 Python 依赖，**不采用** |

所以 `pdf` 的处理是：MCP 用 `pdftoppm` 把**前 ≤3 页**转成 PNG（放在与渲染产物同一根下），返回成 `image` 媒体描述符，走**已经验证过的图片通道**内嵌；卡片同时给出页数与"翻看完整 PDF"按钮，点击走右侧栏——`dsh-client-ui-sidebar-documentpreview` 注册了 `extensions: ["pdf"]`（`client.js:26708`）并内置 pdf.js，这条 fallback 是成立的。

**上限 3 页**与"一轮最多发 3 个"同源：一份 50 页的 PDF 不该变成 50 张图刷屏。

### 9.2 信封在会话日志里原样保留

渲染器要 `JSON.parse(ToolResultNode.content` 里的 text 块 `)`。实测：写 `tests/manual/envelope_survives.mjs` 解压当前会话全部 zstd 帧（2952 帧 / 5053 条记录），在 **742 条 tool/result** 里找到带信封的那条，并断言

```
re-dump matches recorded text: true
```

即记录下来的文本块与 `json.dumps(envelope, indent=2)` **逐字节一致**——`dsh-mcp-client` 的 `projectContent` 只合并相邻文本 run，不碰我们的内容。

> 这个脚本本身也踩了一个坑，值得记下：最初按"记录里出现 `previewMarkdown`"筛选，结果被**本会话自己的命令输出**污染了——我跑过的命令 stdout 也进日志，而搜索脚本的源码里就含这个词。判据必须收紧成"这个文本块能 `JSON.parse` 成带 `runId` 的信封"。

结论：解析是实现细节，不是风险。但 §8 第 1 条（解析失败不得抛异常）仍然保留——契约稳定不等于可以不做防御。

---

## 10. 安装与卸载

复用 `tools/dsh_installer.py` 已经过验证的机制：

- 新增一条 `- insert:` 行挂载 `media-mcp`（`- id: mcp-media`），env 里钉死 python、roots、max-bytes、fs-cwd
- 复制并 `link:` 新插件 `dsh-media-view`，加进 `dsh.profile.bundles`
- 卸载时按同一 id 移除两处，沙盒内断言逐字节还原
- `pin-fs-cwd` 的 cwd 由**一个**变量同时供给 `fs-sandbox.cwd`、Manim 与 media 两个 MCP —— 保证"同盘"这条不变量只有一个来源

---

## 11. 测试策略

| 层 | 覆盖 |
|---|---|
| MCP 纯函数 | MIME 嗅探（含扩展名与 magic 冲突）、kind 分类、reference 构造、六种校验失败、边界值恰好等于上限 |
| MCP 集成 | 真实 stdio 服务端跑一次 `publish_file`，断言信封形状与文件真实存在 |
| client | 离线 harness：每种 kind 的派发、URL 编码（含空格/中文/括号）、进行中态、失败态、解析失败不抛、key 逐字正确、**零写操作** |
| 安装 | insert/remove 幂等、卸载逐字节还原、`fs-cwd` 单一来源 |

断言强度要求：每条测试都要能说清"它拦住的**具体的**错误是什么"。做不到这一点的测试不写。

---

## 12. 明确不做（YAGNI）

- **不动 Manim 的 8 个工具卡片**。它们继续用通用行 + 图片通道，不注册 `tool.call.toolview`。顺手改掉已经验收过的东西是负收益。
- 不做大文件分片、不走 Range、不做流式（20 MiB 是 shipped 硬约束；真要发大文件是另一个课题，需要另一条通道）。
- 不做用户→模型的上传方向（那需要一个不同的入口，与本方案的通道无关）。
- 不加新的右侧栏 tab，复用 `documentpreview`。
- 不做转码/缩略图生成（ffmpeg 是 Manim 那条线的依赖，本通道不引入）。
- **不配 skill**（§3.2：官方做法是把行为写进工具描述；skill 有"加载不上"的失败模式）。
- **不接管 `present` 的 key**，也不动 `conversation.chat.turnTail` 的产物行（§3.1：那是官方交付物体验）。

---

## 13. 判据

1. 模型调用 `mcp__media__publish_file` 后，**视频在对话流里直接播放**。
2. PDF **前 3 页以图片内嵌**（走已验证的图片通道），并有"翻看完整 PDF"按钮打开右侧栏 pdf.js。
3. 任意其它格式有文件名/类型/大小/可打开。
4. 六种失败各有一条可读提示，且**没有任何一条会发出注定失败的引用**。
5. 未覆盖任何 shipped UI：`git grep` 与 Inspect 双重确认我们只占了 `mcp__media__publish_file` 这一个 key；`present` 与 `conversation.chat.turnTail` 未被触碰。
6. `publish_file` 的 `description` 四问齐备（何时发/何时不发/上限个数/超限怎么办），且不依赖任何 skill 被加载。
7. Manim 那条线的两套测试（engine 401 / panel 78）保持全绿。
8. 卸载后 `cordis.patch.yml` 与 `package.json` 逐字节还原。

**这 8 条全部满足，这个特性才算做完。**
