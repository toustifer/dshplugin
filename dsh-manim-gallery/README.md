# dsh-manim-gallery

DSH 左侧栏的**「动画库」面板**：常驻回看 `manim-mcp` 渲染出的全部动画。它是 `D:\myprogram\dshplugin` 三个组件中的第二个（第一个是渲染引擎，第三个是 Skill 与安装器）。

它**只读**：读 `manim-mcp` 写出的 `renders/index.json`，把每条记录渲染成一张卡片，点开用原生视频播放器看 MP4。它不改任何文件、不调用任何 MCP 工具。

---

## 加载方式

DSH 通过三样东西加载一个打包插件，缺一不可：

| 位置 | 作用 |
|---|---|
| `package.json` 的 `dsh.bundle.patch` | 指向 `./cordis.patch.yml`，DSH 据此把本包插入 Cordis 树 |
| `package.json` 的 `dsh.client` | 声明 Client 半的入口（`exports["./client"]`）、`platform: "web"`、以及它依赖的 Client 包 |
| `cordis.patch.yml` | `- insert: [{id: dsh-manim-gallery, name: dsh-manim-gallery}]` |

除此之外，profile 必须知道这个包存在：

1. `~/.dsh/profiles/web/package.json` 的 `dsh.profile.bundles` 数组里要有 `"dsh-manim-gallery"`；
2. 同文件的 `dependencies` 里要有 `"dsh-manim-gallery": "link:C:/Users/<你>/.dsh/plugins/dsh-manim-gallery"`；
3. `~/.dsh/profiles/web/node_modules/dsh-manim-gallery` 必须是指向插件目录的**符号链接**（`install.ps1` 直接建链接，不依赖 pnpm）。

`install.ps1` 会把 1–3 全部做完并备份原文件；`uninstall.ps1` 会精确还原。

**改完必须重启 dsh web 才生效**，然后 `~/.dsh` 下不会自动重载。

---

## 数据通路

```
manim-mcp 渲染完成
   └─→ 更新 renders/index.json（原子替换）
          │
          ▼
面板挂载 / 点刷新
   └─→ fetch("/api/file?path=" + encodeURIComponent("/D:/…/renders/index.json"))
          │  DSH 已鉴权的文件通道，同源 cookie 自动携带
          ▼
卡片缩略图：<img src="/api/file?path=…gif">
详情播放器：<video controls src="/api/file?path=…mp4">
```

`/api/file` 的契约（来自 `dsh-api-session-controller` 的文档）：挂在**已鉴权通道**上，**不受目录包含与 MIME 类别限制**，单文件上限 20MiB，**音视频响应可用**。鉴权靠页面的 `dsh-auth-*` cookie，所以：

- 页面内的 `<img>` / `<video>` / `fetch` 自动带上凭据；
- **裸请求会得到 401**——想手工验证，必须在已登录的浏览器里打开，而不是用 curl。

---

## `RENDER_ROOT` 由 `install.ps1` 改写

`lib/client.js` 里有一行：

```js
const RENDER_ROOT = "D:/myprogram/dshplugin/renders";
```

`install.ps1` 会把这条字符串字面量改写成**与 MCP 的 `MANIM_MCP_RENDER_ROOT` 完全一致**的值。**这一行的形状是约定**：改写用的是 `^(\s*)const RENDER_ROOT = "([^"]*)";$` 这个正则，改动它的写法会让改写静默失效，于是面板读一个不存在的路径，只显示「读不到动画库」。

安装器不会猜：找不到这一行就**直接报错**，而不是继续装下去。

---

## 只读边界（有意的设计决定，不是还没做）

面板**不做删除，也不做重渲染**。

原因是技术性的：**手写打包插件没有 client→host 调用通道**。DSH 的 client→host 调用走的是 Typert Gateway 生成的 Remote 贡献（见 `dsh-api-remotes`），那需要完整的 TypeScript/tsdown 构建管线与声明合并；手写插件可用的桥只有 host→client 的转发事件白名单。删除要写文件系统、重渲染要调用 MCP，两者都必须由 Host 侧发起。

因此这两件事改由 **MCP 侧的 `runs` 工具**承担：用户对模型说「把那张图删了」，模型调用 `runs action=delete`。面板只提供「复制路径」，让用户在资源管理器里自行处理。

**「在右侧打开」不属于写操作，所以它在范围内**：面板把一个 `dsh-resource://file/absolute/...` 资源地址交给 DSH 自带的右侧栏文档预览器（`ctx.sidebarRight.openResource`），由那个预览器渲染 GIF/WebP/PNG——不需要我们自己写预览器，也不需要新造 tab 类型。

- **只交预览产物，不交 MP4**：自带预览器的 MIME 表里有 `gif`/`webp`/`png`，**没有 `video/mp4`**，交 MP4 会开出一个渲染不出内容的 tab。完整视频仍走面板内的 `<video controls>`。
- 先调 `ctx.layout.openRightbar(true, false)` 展开抽屉：`openResource` 是否顺带展开不属于它的契约，显式调用才不会开出一个看不见的 tab。
- 两个服务用 `ctx.get()` **探测**，不写进 `inject`：缺服务时只是少一个按钮，面板照常可用。

代码里也钉了一道：`test/view.test.mjs` 的 `the view never builds a write request` 遍历整棵元素树，断言没有任何 `method:` / POST / DELETE / PUT 字符串。

---

## 依赖

只依赖 DSH 自己提供的 `react` 与 `react-dom`（通过 `window.__ModuleLoader__` 的 `require`）。**没有 npm 依赖，没有构建步骤**——`lib/client.js` 就是最终产物。

开发时需要一个 Node（仅用于跑测试）：`node --version` 应 ≥ 20。

---

## 测试

```powershell
cd D:\myprogram\dshplugin\dsh-manim-gallery
node --test "test/*.test.mjs"
```

离线 harness 在 `test/harness.mjs` 里 mock 了四样东西：

| mock | 为什么 |
|---|---|
| `globalThis.window.__ModuleLoader__` | `client.js` 是脚本，它调用 `load({id, factory})`；harness 用 `new Function` 扮演这个角色 |
| `ctx`（含 `slots.inject` / `slots.register`） | 断言 `apply` 注册了哪两个槽位、参数是什么 |
| `react` | 只需 `createElement` / `useState` / `useEffect` / `useCallback`；`useState` 的 setter 会记录收到的 state，让 effect 的**结果**可断言 |
| `globalThis.fetch` | 断言请求的是哪个 URL，并模拟 404 / 空索引 / 坏 body |

`test/pure.test.mjs` 断言数据变换（路径、URL、相对时间、排序、筛选、读索引），`test/view.test.mjs` 断言 `galleryView(state, actions)` 在四种状态下返回的元素树，`test/page.test.mjs` 断言状态机与接线，`test/style.test.mjs` 断言主题 token 与样式注入的幂等性。

> 注意 Node 22 的 `--test` **不接受目录位置参数**（`node --test test/` 会被当成模块路径而报 `Cannot find module`）。用上面的 glob 形式，或直接给文件路径。

---

## 排错

| 现象 | 先看哪里 |
|---|---|
| 左侧栏没有「动画库」图标 | profile 的 `dsh.profile.bundles` 里有没有 `dsh-manim-gallery`；`node_modules/dsh-manim-gallery` 是不是有效符号链接；重启 web 了吗 |
| 图标在，但面板显示「读不到动画库」 | 面板会把**它尝试读取的绝对路径**显示出来。核对该路径与 `manim-mcp` 的 `MANIM_MCP_RENDER_ROOT` 是否一致；`renders/index.json` 是否存在 |
| 缩略图空白，但面板有卡片 | 在**已登录的浏览器**里直接打开该卡片对应的 `/api/file?path=…`。401 说明鉴权没带上；404 说明产物文件被删了 |
| 详情里没有播放器 | 那条 run 没有 `assets.mp4`（渲染失败，或 MP4 被清理了）。面板会退回显示 GIF 或海报帧 |
| 改了 `RENDER_ROOT` 却没生效 | 重启 web。`client.js` 是启动时加载的，不会热重载 |

---

## 归属

- 设计文档：`../docs/superpowers/specs/2026-09-12-manim-visual-explainer-design.md`（§19）
- 实施计划：`../docs/superpowers/plans/2026-09-12-manim-gallery-panel.md`
- 数据来源：`../manim-mcp`（它写出 `renders/index.json`）
