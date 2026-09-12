# dsh-manim-gallery（组件 2）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 DSH 左侧栏加一个常驻的「动画库」面板，点开是一个全尺寸中央页面：网格预览所有历史动画、搜索筛选排序、点开用视频播放器看 MP4、一键复制路径。

**Architecture:** 一个**手写的 DSH 打包插件**（无构建步骤），Host 半为空，Client 半在 `sidebar.panellist` 上注册一个图标、在 `main` 上注册一个以同一个 id 为 key 的页面。面板**纯前端**拿数据：`fetch("/api/file?path=…index.json")` 读元数据，`<img src="/api/file?path=…gif">` 看动图、`<video controls src="/api/file?path=…mp4">` 看完整视频。**不需要自定义 Host RPC**，因为 `/api/file` 已经挂在 DSH 自己的已鉴权通道上。

**Tech Stack:** 纯 JavaScript（浏览器 ES2022）、`window.__ModuleLoader__.load({id, factory})` 模块格式、React（由 loader 提供）、Node 22 内置 `node:test` 做离线测试。

**Spec:** `docs/superpowers/specs/2026-09-12-manim-visual-explainer-design.md`（§12 通道 C、§19 面板设计）

**参考实现（本机已有，可直接读）**：`C:\Users\15775\.dsh\plugins\dsh-cross-session-modal\` —— 一个已验证可加载的手写 DSH 插件，本计划的包结构与离线测试模式都从它抄。

---

## 关键事实（已查证，不是推断）

这些是设计的全部依据，实现时不要再猜：

| 事实 | 来源 |
|---|---|
| `sidebar.panellist`（list，root 作用域）：「Global panel icons. **Each list id addresses the matching main panel**; the sidebar owns the button and resolves its label from list metadata.」注册参数 `id`(必填) / `order` / `label`；**图标组件收到 ownerProps `{size, active}`** | DSH 槽位目录实查 |
| `main`（keyed，root 作用域）：「Central panel selected by sidebar entry id.」key 域开放，`conversation` 已被占用 | 同上 |
| 布局层真实调用：`renderSlot("main", {}, { entryKey: usePanelInfo((info) => info.activePanelId) ?? "conversation" })`；侧栏对每个 panel 调 `renderSlot("sidebar.panellist", {size, active}, {only: id})` 并 `selectPanel(id)` | `dsh-client-ui-layout` / `dsh-client-ui-sidebar` 源码 |
| 两个槽位的 `replaceRisk` 分别是 `none` 与 `shadows-shipped-ui`，后者只在**占用已存在的 key** 时发生 —— 我们用全新 id，不碰任何 shipped UI | 槽位目录 |
| `GET|HEAD /api/file?path=<绝对路径>` 挂在**已鉴权通道**上；**不受目录包含与 MIME 类别限制**；单文件上限 20MiB；**音视频响应可用** | `dsh-api-session-controller/README.md` 原文 |
| 鉴权是 `dsh-auth-*` cookie 或 `token` 查询参数；**裸请求会 401**（已实测） | `dsh-client-connection` 源码 + 实测 |
| 打包插件的形态：`package.json` 的 `dsh.bundle.patch` + `dsh.client{platform:"web", inject:[...]}`；`cordis.patch.yml` 里 `- insert: [{id, name}]`；`lib/index.js` 是 Host 半、`lib/client.js` 是手写 `window.__ModuleLoader__.load`；**无构建步骤** | `dsh-cross-session-modal` 实读 |
| Client 注册 API：`ctx.slots.inject(name, () => ctx.slots.register(opts, Component))`；keyed 槽位用 `key`，list 槽位用 `id`；模块导出 `apply` 与 `inject` | `dsh-client-ui-cordis` / `dsh-cross-session-modal` 源码 |
| **手写打包插件无法新增 client→host 调用**：client→host 走的是 Typert Gateway 生成的 Remote 贡献，需要完整 TS/tsdown 构建管线。可用桥只有 host→client 的转发事件（`API_REMOTE_FORWARDED_EVENTS` 白名单） | `dsh-api-remotes/README.md` + `dsh-cross-session-modal`（Host 半为空） |

### 由此得出的范围决策：**面板 v1 只读**

面板**不做**删除、不做重渲染，因为它们需要写文件系统或调用 MCP，而手写插件没有 client→host 通道。这两件事改由 **MCP 侧的 `runs` 工具**承担（用户对模型说「把那张图删了」，模型调 `runs action=delete`），面板只提供「复制路径」，让用户在资源管理器里自己处理。

这是对 Spec §19.4 的**范围缩减**，理由如上，需回写 Spec。

---

## 文件结构

```
D:\myprogram\dshplugin\dsh-manim-gallery\
├─ package.json            名称/版本/type/exports/dsh 元数据/peerDependencies
├─ cordis.patch.yml        - insert: [{id: dsh-manim-gallery, name: dsh-manim-gallery}]
├─ README.md               这个组件是什么、怎么被加载、怎么排错
├─ lib\
│  ├─ index.js             Host 半（本组件为空实现）
│  └─ client.js            浏览器半：纯函数 + 纯视图函数 + 两个槽位注册
└─ test\
   ├─ harness.mjs          离线 harness：mock window/ctx/react/fetch，求值 client.js
   ├─ pure.test.mjs        fileUrl / relativeTime / sortRuns / filterRuns / loadIndex
   ├─ view.test.mjs        galleryView 的四种状态 + 图标
   └─ plugin.test.mjs      模块形态、inject、apply 注册的两个槽位
```

**为什么把逻辑拆成纯函数 + 纯视图函数**：`client.js` 在浏览器里跑，但它的**数据变换**与**元素树构造**都是纯的。把 `galleryView(state, actions)` 从 `GalleryPage` 里分出来，测试就能直接断言「给定这个 state，会渲染出什么树」，而不必去测 React 的 hook 语义——hook 那一层只剩「把 state 接上去」这一件事，用一个测试钉住即可。

---

## Task 1: 包骨架 + 离线 harness + 双槽位注册

**Files:**
- Create: `dsh-manim-gallery/package.json`
- Create: `dsh-manim-gallery/cordis.patch.yml`
- Create: `dsh-manim-gallery/lib/index.js`
- Create: `dsh-manim-gallery/lib/client.js`
- Create: `dsh-manim-gallery/test/harness.mjs`
- Test: `dsh-manim-gallery/test/plugin.test.mjs`

- [ ] **Step 1: 写离线 harness**

`dsh-manim-gallery/test/harness.mjs`:

```js
// Offline harness: evaluates the browser half of the plugin against mock Cordis
// surfaces, so the panel can be tested without a browser or a running DSH.
//
// `lib/client.js` is a plain script that calls `window.__ModuleLoader__.load`,
// exactly as the shipped client-bundle format does; `new Function` is how the
// harness plays that script's role.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const PACKAGE_ROOT = resolve(HERE, "..");
export const CLIENT_PATH = resolve(PACKAGE_ROOT, "lib", "client.js");

export function createReactStub() {
	// `hooks.updates` is what makes an effect's *outcome* assertable: the stub has
	// no re-render loop, so a test reads the state object the setter was handed
	// rather than the tree a real React would have painted. The setter applies a
	// functional update to the captured initial value, which is exact for the
	// single-update sequences these tests exercise and wrong for a chain — do not
	// use it to test reducer-like behaviour.
	const hooks = { states: [], setters: [], updates: [], effects: [], refs: [] };
	return {
		hooks,
		Fragment: Symbol.for("react.fragment"),
		createElement(type, props, ...children) {
			return { type, props: { ...(props ?? {}), children: children.flat(Infinity) } };
		},
		useState(initial) {
			const value = typeof initial === "function" ? initial() : initial;
			hooks.states.push(value);
			const setter = (next) => {
				const resolved = typeof next === "function" ? next(value) : next;
				hooks.updates.push(resolved);
				return resolved;
			};
			hooks.setters.push(setter);
			return [value, setter];
		},
		useEffect(fn, deps) {
			hooks.effects.push({ fn, deps });
		},
		useMemo(fn) {
			return fn();
		},
		useCallback(fn) {
			return fn;
		},
		useRef(value) {
			const ref = { current: value };
			hooks.refs.push(ref);
			return ref;
		},
	};
}

export function createCtx() {
	const registrations = [];
	return {
		registrations,
		/** The registration for one slot, matched by list `id` or keyed `key`. */
		find(name) {
			return registrations.find((entry) => entry.options.name === name);
		},
		ctx: {
			slots: {
				inject(key, callback) {
					return callback();
				},
				register(options, component) {
					registrations.push({ options, component });
					return () => {};
				},
			},
			get() {
				return undefined;
			},
			on() {
				return () => {};
			},
		},
	};
}

/** Evaluate lib/client.js and return the captured module entry plus its exports. */
export function loadClient({ fetchImpl } = {}) {
	let captured = null;
	globalThis.window = {
		__ModuleLoader__: {
			load(entry) {
				captured = entry;
			},
		},
		location: { protocol: "http:", origin: "http://127.0.0.1:3080" },
		addEventListener() {},
		removeEventListener() {},
	};
	globalThis.fetch =
		fetchImpl ??
		(async () => ({
			ok: true,
			status: 200,
			json: async () => ({ version: 1, updatedAt: null, runs: [] }),
		}));

	const react = createReactStub();
	const loader = (specifier) => {
		if (specifier === "react") return react;
		throw new Error(`unexpected require(${JSON.stringify(specifier)})`);
	};

	new Function("require", readFileSync(CLIENT_PATH, "utf8"))(loader);
	if (captured === null) throw new Error("client.js did not call __ModuleLoader__.load");
	return { entry: captured, plugin: captured.factory(loader), react };
}

/** A run entry shaped like the one manim-mcp writes into renders/index.json. */
export function makeRun(overrides = {}) {
	return {
		runId: "20260912-153012-a1b2",
		tool: "equation",
		sceneName: "EquationScene",
		title: "欧拉恒等式",
		status: "ok",
		quality: "draft",
		createdAt: "2026-09-12T15:30:12+08:00",
		durationSec: 10.4,
		renderSeconds: 9.8,
		assets: {
			mp4: "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\EquationScene.mp4",
			preview: "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\EquationScene.gif",
			previewKind: "gif",
			poster: "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\EquationScene.png",
		},
		previewUrlPath: "/D:/myprogram/dshplugin/renders/20260912-153012-a1b2/out/EquationScene.gif",
		args: { steps: 3 },
		warnings: [],
		...overrides,
	};
}
```

- [ ] **Step 2: 写失败测试**

`dsh-manim-gallery/test/plugin.test.mjs`:

```js
import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, loadClient } from "./harness.mjs";

test("the module registers itself under the package name", () => {
	const { entry } = loadClient();
	assert.equal(entry.id, "dsh-manim-gallery");
	assert.equal(typeof entry.factory, "function");
});

test("the plugin declares the slots service as its only hard dependency", () => {
	const { plugin } = loadClient();
	assert.deepEqual(plugin.inject, ["slots"]);
	assert.equal(typeof plugin.apply, "function");
});

test("apply registers a global panel icon and a matching main panel", () => {
	const { plugin } = loadClient();
	const { ctx, registrations } = createCtx();
	plugin.apply(ctx);

	assert.equal(registrations.length, 2);

	const icon = registrations.find((r) => r.options.name === "sidebar.panellist");
	const page = registrations.find((r) => r.options.name === "main");
	assert.ok(icon, "sidebar.panellist was not registered");
	assert.ok(page, "main was not registered");

	// The sidebar resolves the button from list metadata, and that same id is what
	// the layout dispatches into `main` — the two must be one string.
	assert.equal(icon.options.id, "manim-gallery");
	assert.equal(page.options.key, "manim-gallery");
	assert.equal(icon.options.label, "动画库");
	assert.ok(Number.isFinite(icon.options.order));
});
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/*.test.mjs"`
Expected: FAIL — `ENOENT: no such file or directory, open '...\lib\client.js'`

- [ ] **Step 4: 写最小实现**

`dsh-manim-gallery/package.json`:

```json
{
  "name": "dsh-manim-gallery",
  "version": "0.1.0",
  "description": "DeepSeek Harness 左侧栏「动画库」面板：常驻回看 manim-mcp 渲染出的全部动画",
  "type": "module",
  "main": "lib/index.js",
  "exports": {
    ".": "./lib/index.js",
    "./client": "./lib/client.js",
    "./package.json": "./package.json"
  },
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    },
    "client": {
      "inject": [
        "@deepseek-ai/dsh-api-remotes",
        "@deepseek-ai/dsh-client-ui-renderer",
        "@deepseek-ai/dsh-client-ui-layout"
      ],
      "platform": "web"
    }
  },
  "scripts": {
    "test": "node --test \"test/*.test.mjs\""
  },
  "license": "MIT",
  "peerDependencies": {
    "@deepseek-ai/cordis": "^4.0.2"
  }
}
```

`dsh-manim-gallery/cordis.patch.yml`:

```yaml
- insert:
    - id: dsh-manim-gallery
      name: dsh-manim-gallery
```

`dsh-manim-gallery/lib/index.js`:

```js
/**
 * Host half.
 *
 * This plugin has nothing to do on the Host: the panel reads `renders/index.json`
 * through the already-authenticated `/api/file` channel, so it needs no Host
 * service, no RPC, and no filesystem access of its own. The entry exists because
 * the Cordis bundle expects a Host-side module, and it is the place a future
 * Host-side feature would go.
 */
export function apply(ctx) {
	// Intentionally empty.
}
```

`dsh-manim-gallery/lib/client.js`:

```js
window.__ModuleLoader__.load({
	id: "dsh-manim-gallery",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });

		const react = require("react");
		const h = react.createElement;

		/** The panel id. The sidebar entry and the `main` key must be this one string. */
		const PANEL_ID = "manim-gallery";

		function GalleryIcon(props) {
			return h("span", { className: "manim-gallery__glyph", "aria-hidden": "true" }, "▦");
		}

		function GalleryPage() {
			return h("div", { className: "manim-gallery" }, "动画库");
		}

		function apply(ctx) {
			ctx.slots.inject("sidebar.panellist", () =>
				ctx.slots.register(
					{ name: "sidebar.panellist", id: PANEL_ID, order: 40, label: "动画库" },
					GalleryIcon
				)
			);
			ctx.slots.inject("main", () =>
				ctx.slots.register({ name: "main", key: PANEL_ID }, GalleryPage)
			);
		}

		exports.apply = apply;
		exports.inject = ["slots"];
		return module.exports;
	},
});
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/*.test.mjs"`
Expected: PASS（3 passed）

- [ ] **Step 6: 提交**

```bash
git add dsh-manim-gallery
git commit -m "feat(manim-gallery): 包骨架、离线 harness 与双槽位注册"
```

---

## Task 2: 纯函数层 —— 路径、URL、时间、排序、筛选、读索引

**Files:**
- Modify: `dsh-manim-gallery/lib/client.js`
- Test: `dsh-manim-gallery/test/pure.test.mjs`

- [ ] **Step 1: 写失败测试**

`dsh-manim-gallery/test/pure.test.mjs`:

```js
import assert from "node:assert/strict";
import { test } from "node:test";

import { makeRun } from "./harness.mjs";
import { loadClient } from "./harness.mjs";

const { plugin } = loadClient();
const {
	RENDER_ROOT,
	INDEX_PATH,
	fileUrl,
	indexUrl,
	relativeTime,
	sortRuns,
	filterRuns,
	loadIndex,
	runTool,
} = plugin.__internals;

test("the render root is a slash path the Host can serve", () => {
	assert.match(RENDER_ROOT, /^[A-Za-z]:\//);
	assert.equal(INDEX_PATH, `${RENDER_ROOT}/index.json`);
});

test("fileUrl routes an absolute path through the authenticated file endpoint", () => {
	const url = fileUrl("D:\\myprogram\\dshplugin\\renders\\a\\out\\S.gif");
	assert.equal(
		url,
		"/api/file?path=" + encodeURIComponent("/D:/myprogram/dshplugin/renders/a/out/S.gif")
	);
});

test("fileUrl accepts a path that is already in slash form", () => {
	assert.equal(fileUrl("/D:/r/a.gif"), "/api/file?path=" + encodeURIComponent("/D:/r/a.gif"));
});

test("fileUrl does not double the leading slash", () => {
	assert.ok(!fileUrl("/D:/a.gif").includes(encodeURIComponent("//D:")));
});

test("fileUrl escapes characters that would break the query string", () => {
	const url = fileUrl("D:\\my program\\a&b.gif");
	assert.ok(!url.includes(" "));
	assert.ok(!url.includes("&b"));
});

test("indexUrl points at the render root's index", () => {
	assert.equal(indexUrl(), fileUrl(INDEX_PATH));
});

test("relativeTime speaks in the units a reader scans for", () => {
	const now = Date.parse("2026-09-12T20:00:00+08:00");
	assert.equal(relativeTime("2026-09-12T19:59:30+08:00", now), "刚刚");
	assert.equal(relativeTime("2026-09-12T19:52:00+08:00", now), "8 分钟前");
	assert.equal(relativeTime("2026-09-12T18:00:00+08:00", now), "2 小时前");
	assert.equal(relativeTime("2026-09-11T20:00:00+08:00", now), "昨天");
	assert.equal(relativeTime("2026-09-05T20:00:00+08:00", now), "7 天前");
	assert.equal(relativeTime("2026-06-01T20:00:00+08:00", now), "2026-06-01");
});

test("relativeTime tolerates a missing or unparsable timestamp", () => {
	assert.equal(relativeTime(null, Date.now()), "");
	assert.equal(relativeTime("not a date", Date.now()), "");
});

test("sortRuns defaults to newest first", () => {
	const runs = [
		makeRun({ runId: "a", createdAt: "2026-09-12T10:00:00+08:00" }),
		makeRun({ runId: "b", createdAt: "2026-09-12T12:00:00+08:00" }),
		makeRun({ runId: "c", createdAt: "2026-09-12T11:00:00+08:00" }),
	];
	assert.deepEqual(sortRuns(runs, "newest").map(runTool), ["b", "c", "a"]);
});

test("sortRuns can order by duration", () => {
	const runs = [
		makeRun({ runId: "a", durationSec: 5 }),
		makeRun({ runId: "b", durationSec: 20 }),
		makeRun({ runId: "c", durationSec: 12 }),
	];
	assert.deepEqual(sortRuns(runs, "longest").map(runTool), ["b", "c", "a"]);
});

test("sortRuns does not mutate its input", () => {
	const runs = [
		makeRun({ runId: "a", createdAt: "2026-09-12T10:00:00+08:00" }),
		makeRun({ runId: "b", createdAt: "2026-09-12T12:00:00+08:00" }),
	];
	sortRuns(runs, "newest");
	assert.deepEqual(runs.map(runTool), ["a", "b"]);
});

test("filterRuns hides failed runs by default", () => {
	const runs = [makeRun({ runId: "a" }), makeRun({ runId: "b", status: "failed" })];
	assert.deepEqual(filterRuns(runs, {}).map(runTool), ["a"]);
});

test("filterRuns can show failed runs on request", () => {
	const runs = [makeRun({ runId: "a" }), makeRun({ runId: "b", status: "failed" })];
	assert.deepEqual(filterRuns(runs, { includeFailed: true }).map(runTool), ["a", "b"]);
});

test("filterRuns narrows by tool", () => {
	const runs = [makeRun({ runId: "a", tool: "equation" }), makeRun({ runId: "b", tool: "graph" })];
	assert.deepEqual(filterRuns(runs, { tool: "graph" }).map(runTool), ["b"]);
});

test("filterRuns searches title and tool, case-insensitively", () => {
	const runs = [
		makeRun({ runId: "a", title: "欧拉恒等式", tool: "equation" }),
		makeRun({ runId: "b", title: "sin 与切线", tool: "graph" }),
	];
	assert.deepEqual(filterRuns(runs, { query: "切线" }).map(runTool), ["b"]);
	assert.deepEqual(filterRuns(runs, { query: "GRAPH" }).map(runTool), ["b"]);
	assert.deepEqual(filterRuns(runs, { query: "不存在" }).map(runTool), []);
});

test("filterRuns treats a blank query as no filter", () => {
	const runs = [makeRun({ runId: "a" })];
	assert.equal(filterRuns(runs, { query: "   " }).length, 1);
});

test("filterRuns survives entries with missing fields", () => {
	const runs = [{ runId: "x" }, makeRun({ runId: "a" })];
	assert.deepEqual(filterRuns(runs, {}).map(runTool), ["x", "a"]);
});

test("loadIndex asks for the index through fileUrl", async () => {
	const seen = [];
	const result = await loadIndex(async (url) => {
		seen.push(url);
		return { ok: true, status: 200, json: async () => ({ updatedAt: "t", runs: [makeRun()] }) };
	});
	assert.deepEqual(seen, [indexUrl()]);
	assert.equal(result.runs.length, 1);
	assert.equal(result.updatedAt, "t");
});

test("loadIndex reports a non-OK response with its status", async () => {
	await assert.rejects(
		() => loadIndex(async () => ({ ok: false, status: 404, json: async () => ({}) })),
		/404/
	);
});

test("loadIndex rejects a body that is not an object with runs", async () => {
	await assert.rejects(
		() => loadIndex(async () => ({ ok: true, status: 200, json: async () => [1, 2] })),
		/runs/
	);
});

test("loadIndex tolerates a missing updatedAt", async () => {
	const result = await loadIndex(async () => ({ ok: true, status: 200, json: async () => ({ runs: [] }) }));
	assert.equal(result.updatedAt, null);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/pure.test.mjs"`
Expected: FAIL — `TypeError: Cannot destructure property 'RENDER_ROOT' of 'plugin.__internals' as it is undefined`

- [ ] **Step 3: 写实现**

在 `lib/client.js` 的 `PANEL_ID` 之后插入：

```js
		/**
		 * Where manim-mcp writes its runs. `install.ps1` rewrites the string literal
		 * on the next line so the panel and the MCP always agree on one root; keep
		 * this line's shape stable or that rewrite silently stops matching.
		 */
		const RENDER_ROOT = "D:/myprogram/dshplugin/renders";
		const INDEX_PATH = `${RENDER_ROOT}/index.json`;

		/** Route one absolute Host path through DSH's authenticated file endpoint. */
		function fileUrl(absolutePath) {
			const slashed = String(absolutePath).replace(/\\/g, "/");
			const rooted = slashed.startsWith("/") ? slashed : `/${slashed}`;
			return `/api/file?path=${encodeURIComponent(rooted)}`;
		}

		function indexUrl() {
			return fileUrl(INDEX_PATH);
		}

		const MINUTE = 60_000;
		const HOUR = 60 * MINUTE;
		const DAY = 24 * HOUR;

		function relativeTime(iso, now = Date.now()) {
			const then = Date.parse(iso ?? "");
			if (!Number.isFinite(then)) return "";
			const delta = now - then;
			if (delta < MINUTE) return "刚刚";
			if (delta < HOUR) return `${Math.floor(delta / MINUTE)} 分钟前`;
			if (delta < DAY) return `${Math.floor(delta / HOUR)} 小时前`;
			const days = Math.floor(delta / DAY);
			if (days === 1) return "昨天";
			if (days < 30) return `${days} 天前`;
			return new Date(then).toISOString().slice(0, 10);
		}

		function runTool(run) {
			return run?.runId ?? "";
		}

		const SORTERS = {
			newest: (a, b) => String(b?.createdAt ?? "").localeCompare(String(a?.createdAt ?? "")),
			oldest: (a, b) => String(a?.createdAt ?? "").localeCompare(String(b?.createdAt ?? "")),
			longest: (a, b) => (b?.durationSec ?? 0) - (a?.durationSec ?? 0),
			shortest: (a, b) => (a?.durationSec ?? 0) - (b?.durationSec ?? 0),
		};

		function sortRuns(runs, mode = "newest") {
			const compare = SORTERS[mode] ?? SORTERS.newest;
			return [...runs].sort(compare);
		}

		function filterRuns(runs, { query = "", tool = "", includeFailed = false } = {}) {
			const needle = String(query).trim().toLowerCase();
			return runs.filter((run) => {
				if (!includeFailed && run?.status === "failed") return false;
				if (tool && run?.tool !== tool) return false;
				if (!needle) return true;
				const haystack = `${run?.title ?? ""} ${run?.tool ?? ""}`.toLowerCase();
				return haystack.includes(needle);
			});
		}

		async function loadIndex(fetchImpl = globalThis.fetch) {
			const response = await fetchImpl(indexUrl());
			if (!response?.ok) {
				throw new Error(`读取 index.json 失败：HTTP ${response?.status ?? "?"}`);
			}
			const body = await response.json();
			if (body === null || typeof body !== "object" || !Array.isArray(body.runs)) {
				throw new Error("index.json 里没有 runs 数组");
			}
			return { runs: body.runs, updatedAt: body.updatedAt ?? null };
		}
```

并把导出改成：

```js
		exports.apply = apply;
		exports.inject = ["slots"];
		exports.__internals = {
			PANEL_ID,
			RENDER_ROOT,
			INDEX_PATH,
			fileUrl,
			indexUrl,
			relativeTime,
			runTool,
			sortRuns,
			filterRuns,
			loadIndex,
		};
		return module.exports;
```

> `__internals` 存在的原因：这些函数要在浏览器里跑，但它们的逻辑是纯的，暴露出来让离线 harness 能直接断言。`lib/client.js` 里没有任何一处会读它。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/*.test.mjs"`
Expected: PASS（3 + 21 passed）

- [ ] **Step 5: 提交**

```bash
git add dsh-manim-gallery
git commit -m "feat(manim-gallery): 纯函数层（路径/URL/时间/排序/筛选/读索引）"
```

---

## Task 3: 视图层 —— 四种状态的元素树

**Files:**
- Modify: `dsh-manim-gallery/lib/client.js`
- Test: `dsh-manim-gallery/test/view.test.mjs`

- [ ] **Step 1: 写失败测试**

`dsh-manim-gallery/test/view.test.mjs`:

```js
import assert from "node:assert/strict";
import { test } from "node:test";

import { loadClient, makeRun } from "./harness.mjs";

const { plugin } = loadClient();
const { galleryView, galleryIcon } = plugin.__internals;

const NOOP = () => {};

function walk(node, out = []) {
	if (node === null || node === undefined || node === false) return out;
	if (Array.isArray(node)) {
		for (const child of node) walk(child, out);
		return out;
	}
	if (typeof node === "object" && "type" in node) {
		out.push(node);
		walk(node.props?.children, out);
		return out;
	}
	return out;
}

const textOf = (node) =>
	walk(node)
		.flatMap((el) => (Array.isArray(el.props?.children) ? el.props.children : []))
		.filter((child) => typeof child === "string")
		.join(" ");

test("an empty library explains what to do next", () => {
	const tree = galleryView({ phase: "empty", runs: [], selected: null }, actions());
	assert.match(textOf(tree), /还没有动画/);
});

test("a load failure shows the reason and offers a retry", () => {
	const acts = actions();
	const tree = galleryView(
		{ phase: "error", runs: [], selected: null, error: "HTTP 404" },
		acts
	);
	assert.match(textOf(tree), /HTTP 404/);
	assert.ok(walk(tree).some((el) => el.props?.onClick === acts.refresh));
});

test("every run becomes a card with its preview, title and relative time", () => {
	const run = makeRun();
	const tree = galleryView({ phase: "ready", runs: [run], selected: null }, actions());
	const images = walk(tree).filter((el) => el.type === "img");
	assert.equal(images.length, 1);
	assert.ok(images[0].props.src.startsWith("/api/file?path="));
	assert.match(textOf(tree), /欧拉恒等式/);
});

test("a failed run is marked rather than hidden silently", () => {
	const run = makeRun({ status: "failed", title: "崩掉的一次" });
	const tree = galleryView(
		{ phase: "ready", runs: [run], selected: null, includeFailed: true },
		actions()
	);
	assert.match(textOf(tree), /失败/);
});

test("a run without a preview still renders a card", () => {
	const run = makeRun({ assets: { mp4: "D:\\r\\a.mp4" } });
	const tree = galleryView({ phase: "ready", runs: [run], selected: null }, actions());
	assert.equal(walk(tree).filter((el) => el.type === "img").length, 0);
	assert.match(textOf(tree), /欧拉恒等式/);
});

test("clicking a card selects that run", () => {
	const run = makeRun();
	const acts = actions();
	const tree = galleryView({ phase: "ready", runs: [run], selected: null }, acts);
	// Not "the first element with an onClick": the toolbar renders before the grid
	// and its refresh button would be found first.
	const card = walk(tree).find((el) => el.props?.className === "manim-gallery__card");
	assert.ok(card, "no card was rendered");
	card.props.onClick();
	assert.deepEqual(acts.selected, ["20260912-153012-a1b2"]);
});

test("the detail view plays the MP4 with native controls", () => {
	const run = makeRun();
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, actions());
	const video = walk(tree).find((el) => el.type === "video");
	assert.ok(video, "the detail view must offer the MP4");
	assert.equal(video.props.controls, true);
	assert.ok(video.props.src.startsWith("/api/file?path="));
	assert.ok(video.props.src.includes(encodeURIComponent(".mp4")));
});

test("the detail view falls back to the poster when there is no MP4", () => {
	const run = makeRun({
		assets: {
			preview: "D:\\r\\a.gif",
			previewKind: "gif",
			poster: "D:\\r\\a.png",
		},
	});
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, actions());
	assert.equal(walk(tree).find((el) => el.type === "video"), undefined);
	assert.ok(walk(tree).some((el) => el.type === "img"));
});

test("the detail view shows the metadata a reader would ask for", () => {
	const run = makeRun();
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, actions());
	const body = textOf(tree);
	assert.match(body, /equation/);
	assert.match(body, /draft/);
	assert.match(body, /10\.4/);
});

test("the detail view offers a way back and a way to copy the path", () => {
	const run = makeRun();
	const acts = actions();
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, acts);
	const buttons = walk(tree).filter((el) => typeof el.props?.onClick === "function");
	assert.ok(buttons.some((el) => el.props.onClick === acts.back));
	assert.ok(buttons.some((el) => el.props.onClick === acts.copyPath));
});

test("a selection that is no longer in the list falls back to the grid", () => {
	const tree = galleryView(
		{ phase: "ready", runs: [makeRun()], selected: "gone" },
		actions()
	);
	assert.equal(walk(tree).find((el) => el.type === "video"), undefined);
	assert.match(textOf(tree), /欧拉恒等式/);
});

test("the toolbar exposes search, tool filter, sort and refresh", () => {
	const acts = actions();
	const tree = galleryView({ phase: "ready", runs: [makeRun()], selected: null }, acts);
	const controls = walk(tree);
	assert.ok(controls.some((el) => el.type === "input"));
	assert.ok(controls.some((el) => el.type === "select"));
	assert.ok(controls.some((el) => el.props?.onClick === acts.refresh));
});

test("the icon sizes itself from the sidebar and reflects the active state", () => {
	const idle = galleryIcon({ size: 18, active: false });
	const active = galleryIcon({ size: 16, active: true });
	assert.equal(idle.props.width, 18);
	assert.equal(active.props.width, 16);
	assert.notEqual(idle.props.className, active.props.className);
	assert.match(idle.props.className, /manim-gallery__glyph/);
});

test("the view never builds a write request", () => {
	// The panel is read-only by construction: a hand-written packaged plugin has no
	// client-to-host call path, so anything that mutates state belongs on the MCP.
	const tree = galleryView(
		{ phase: "ready", runs: [makeRun()], selected: makeRun().runId },
		actions()
	);
	for (const el of walk(tree)) {
		for (const value of Object.values(el.props ?? {})) {
			if (typeof value === "string") {
				assert.ok(!/method\s*:|POST|DELETE|PUT/i.test(value));
			}
		}
	}
});

function actions() {
	const acts = {
		selected: [],
		refresh: () => {},
		select: (runId) => acts.selected.push(runId),
		back: () => {},
		copyPath: () => {},
		setQuery: () => {},
		setTool: () => {},
		setSort: () => {},
		setIncludeFailed: () => {},
	};
	return acts;
}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/view.test.mjs"`
Expected: FAIL — `TypeError: galleryView is not a function`

- [ ] **Step 3: 写实现**

在 `lib/client.js` 的 `loadIndex` 之后插入：

```js
		const TOOL_LABELS = {
			equation: "公式推导",
			graph: "函数图像",
			diagram: "流程结构",
			compare: "左右对照",
			render: "自定义",
		};

		function runTitle(run) {
			return run?.title || run?.sceneName || run?.runId || "(无标题)";
		}

		function runPreviewUrl(run) {
			const path = run?.assets?.preview;
			return typeof path === "string" && path ? fileUrl(path) : null;
		}

		function galleryIcon({ size = 18, active = false } = {}) {
			// A glyph rather than an image: the sidebar gives an exact square edge and
			// expects the cell to paint inside it, and an inline SVG scales to whatever
			// size the collapsed rail or the expanded row asks for.
			return h(
				"svg",
				{
					className: `manim-gallery__glyph${active ? " is-active" : ""}`,
					width: size,
					height: size,
					viewBox: "0 0 24 24",
					fill: "none",
					stroke: "currentColor",
					strokeWidth: 1.8,
					"aria-hidden": "true",
				},
				h("rect", { key: "a", x: 3, y: 3, width: 18, height: 18, rx: 3 }),
				h("path", { key: "b", d: "M3 14h18" }),
				h("path", { key: "c", d: "M12 14v7" })
			);
		}

		function toolbar(state, actions) {
			return h(
				"div",
				{ className: "manim-gallery__toolbar", key: "toolbar" },
				h("input", {
					key: "query",
					className: "manim-gallery__search",
					type: "search",
					placeholder: "搜索标题或类型…",
					value: state.query ?? "",
					onChange: (event) => actions.setQuery(event.target.value),
				}),
				h(
					"select",
					{
						key: "tool",
						className: "manim-gallery__select",
						value: state.tool ?? "",
						onChange: (event) => actions.setTool(event.target.value),
					},
					h("option", { key: "all", value: "" }, "全部类型"),
					...Object.entries(TOOL_LABELS).map(([value, label]) =>
						h("option", { key: value, value }, label)
					)
				),
				h(
					"select",
					{
						key: "sort",
						className: "manim-gallery__select",
						value: state.sort ?? "newest",
						onChange: (event) => actions.setSort(event.target.value),
					},
					h("option", { key: "newest", value: "newest" }, "最新优先"),
					h("option", { key: "oldest", value: "oldest" }, "最早优先"),
					h("option", { key: "longest", value: "longest" }, "最长优先"),
					h("option", { key: "shortest", value: "shortest" }, "最短优先")
				),
				h(
					"label",
					{ key: "failed", className: "manim-gallery__toggle" },
					h("input", {
						type: "checkbox",
						checked: Boolean(state.includeFailed),
						onChange: (event) => actions.setIncludeFailed(event.target.checked),
					}),
					"显示失败"
				),
				h(
					"button",
					{
						key: "refresh",
						className: "manim-gallery__button",
						type: "button",
						onClick: actions.refresh,
					},
					"刷新"
				)
			);
		}

		function card(run, actions) {
			const preview = runPreviewUrl(run);
			return h(
				"button",
				{
					key: run.runId,
					className: "manim-gallery__card",
					type: "button",
					onClick: () => actions.select(run.runId),
				},
				preview
					? h("img", {
							className: "manim-gallery__thumb",
							src: preview,
							alt: "",
							loading: "lazy",
						})
					: h("div", { className: "manim-gallery__thumb is-missing" }, "无预览"),
				h("div", { className: "manim-gallery__cardTitle" }, runTitle(run)),
				h(
					"div",
					{ className: "manim-gallery__cardMeta" },
					TOOL_LABELS[run.tool] ?? run.tool ?? "",
					run.status === "failed" ? h("span", { className: "is-failed" }, " · 失败") : null,
					run.durationSec ? ` · ${round1(run.durationSec)}s` : "",
					` · ${relativeTime(run.createdAt)}`
				)
			);
		}

		function round1(value) {
			return Math.round(Number(value) * 10) / 10;
		}

		function detail(run, actions) {
			const mp4 = run?.assets?.mp4;
			const preview = runPreviewUrl(run);
			const poster = run?.assets?.poster;
			return h(
				"div",
				{ className: "manim-gallery__detail", key: "detail" },
				h(
					"div",
					{ className: "manim-gallery__detailBar", key: "bar" },
					h(
						"button",
						{ className: "manim-gallery__button", type: "button", onClick: actions.back },
						"← 返回"
					),
					h("h2", { className: "manim-gallery__detailTitle" }, runTitle(run)),
					h(
						"button",
						{
							className: "manim-gallery__button",
							type: "button",
							onClick: () => actions.copyPath(mp4 ?? run?.assets?.preview ?? ""),
						},
						"复制路径"
					)
				),
				mp4
					? h("video", {
							key: "player",
							className: "manim-gallery__player",
							src: fileUrl(mp4),
							controls: true,
							preload: "metadata",
							poster: poster ? fileUrl(poster) : undefined,
						})
					: preview
						? h("img", {
								key: "player",
								className: "manim-gallery__player",
								src: preview,
								alt: runTitle(run),
							})
						: h("div", { key: "player", className: "manim-gallery__player is-missing" }, "这次没有留下产物"),
				h(
					"dl",
					{ className: "manim-gallery__facts", key: "facts" },
					fact("类型", TOOL_LABELS[run.tool] ?? run.tool ?? "—"),
					fact("状态", run.status === "failed" ? "失败" : "成功"),
					fact("画质", run.quality ?? "—"),
					fact("时长", run.durationSec ? `${round1(run.durationSec)} 秒` : "—"),
					fact("渲染耗时", run.renderSeconds ? `${round1(run.renderSeconds)} 秒` : "—"),
					fact("生成时间", run.createdAt ?? "—"),
					fact("runId", run.runId ?? "—"),
					fact("预览路径", run.assets?.preview ?? "—"),
					fact("视频路径", run.assets?.mp4 ?? "—")
				)
			);
		}

		function fact(term, value) {
			return [h("dt", { key: `${term}-t` }, term), h("dd", { key: `${term}-d` }, String(value))];
		}

		/**
		 * The whole panel as a function of state.
		 *
		 * Keeping the tree construction pure is what makes the panel testable
		 * offline: the test hands in a state object and asserts on the elements that
		 * come back, instead of trying to drive React.
		 */
		function galleryView(state, actions) {
			const runs = state.runs ?? [];
			const selected = runs.find((run) => run.runId === state.selected) ?? null;

			if (state.phase === "loading") {
				return h("div", { className: "manim-gallery" }, h("p", null, "正在读取动画库…"));
			}
			if (state.phase === "error") {
				return h(
					"div",
					{ className: "manim-gallery" },
					h("p", { className: "manim-gallery__error" }, `读不到动画库：${state.error ?? "未知错误"}`),
					h("p", { className: "manim-gallery__hint" }, `尝试读取：${INDEX_PATH}`),
					h(
						"button",
						{ className: "manim-gallery__button", type: "button", onClick: actions.refresh },
						"重试"
					)
				);
			}
			if (state.phase === "empty") {
				return h(
					"div",
					{ className: "manim-gallery" },
					h("p", null, "还没有动画。"),
					h("p", { className: "manim-gallery__hint" }, "去问一个值得画的问题吧。")
				);
			}
			if (selected) {
				return h(
					"div",
					{ className: "manim-gallery" },
					toolbar(state, actions),
					detail(selected, actions)
				);
			}
			return h(
				"div",
				{ className: "manim-gallery" },
				toolbar(state, actions),
				h("div", { className: "manim-gallery__grid", key: "grid" }, ...runs.map((run) => card(run, actions)))
			);
		}
```

并把 `__internals` 补上 `galleryIcon`、`galleryView`、`runTitle`、`runPreviewUrl`、`TOOL_LABELS`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/*.test.mjs"`
Expected: PASS（24 + 14 passed）

- [ ] **Step 5: 提交**

```bash
git add dsh-manim-gallery
git commit -m "feat(manim-gallery): 视图层（空态/错误态/网格/详情 + 图标）"
```

---

## Task 4: 把视图接到 React 上

**Files:**
- Modify: `dsh-manim-gallery/lib/client.js`
- Test: `dsh-manim-gallery/test/page.test.mjs`

- [ ] **Step 1: 写失败测试**

`dsh-manim-gallery/test/page.test.mjs`:

```js
import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, loadClient, makeRun } from "./harness.mjs";

const { plugin } = loadClient();

test("the page component mounts without fetching during render", () => {
	const calls = [];
	const loaded = loadClient({
		fetchImpl: async (url) => {
			calls.push(url);
			return { ok: true, status: 200, json: async () => ({ runs: [] }) };
		},
	});
	const { ctx, registrations } = createCtx();
	loaded.plugin.apply(ctx);
	const page = registrations.find((r) => r.options.name === "main");
	assert.equal(typeof page.component, "function");

	page.component({});
	assert.deepEqual(calls, [], "the render pass must not touch the network");
	assert.equal(loaded.react.hooks.effects.length, 1, "exactly one effect was registered");
});

test("the effect fetches the index and tolerates a failure", async () => {
	const calls = [];
	const loaded = loadClient({
		fetchImpl: async (url) => {
			calls.push(url);
			return { ok: false, status: 404, json: async () => ({}) };
		},
	});
	const { ctx, registrations } = createCtx();
	loaded.plugin.apply(ctx);
	const page = registrations.find((r) => r.options.name === "main");
	page.component({});

	const effect = loaded.react.hooks.effects[0];
	assert.equal(typeof effect.fn, "function");
	await effect.fn();
	assert.equal(calls.length, 1);
	assert.ok(calls[0].startsWith("/api/file?path="));

	const final = loaded.react.hooks.updates.at(-1);
	assert.equal(final.phase, "error");
	assert.match(final.error, /404/);
});

test("a successful effect hands the runs to the view", async () => {
	const loaded = loadClient({
		fetchImpl: async () => ({
			ok: true,
			status: 200,
			json: async () => ({ updatedAt: "t", runs: [makeRun()] }),
		}),
	});
	const { ctx, registrations } = createCtx();
	loaded.plugin.apply(ctx);
	registrations.find((r) => r.options.name === "main").component({});
	await loaded.react.hooks.effects[0].fn();

	const final = loaded.react.hooks.updates.at(-1);
	assert.equal(final.phase, "ready");
	assert.equal(final.runs.length, 1);
	assert.equal(final.error, null);
});

test("an empty index lands on the empty state, not the grid", async () => {
	const loaded = loadClient({
		fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ runs: [] }) }),
	});
	const { ctx, registrations } = createCtx();
	loaded.plugin.apply(ctx);
	registrations.find((r) => r.options.name === "main").component({});
	await loaded.react.hooks.effects[0].fn();
	assert.equal(loaded.react.hooks.updates.at(-1).phase, "empty");
});

test("copyToClipboard writes the given text", async () => {
	const written = [];
	const clipboard = { writeText: async (text) => written.push(text) };
	await plugin.__internals.copyToClipboard("D:\\r\\a.mp4", clipboard);
	assert.deepEqual(written, ["D:\\r\\a.mp4"]);
});

test("copyToClipboard is silent when there is no clipboard to write to", async () => {
	await plugin.__internals.copyToClipboard("x", undefined);
	await plugin.__internals.copyToClipboard("x", {});
});

test("copyToClipboard swallows a rejected write", async () => {
	const clipboard = {
		writeText: async () => {
			throw new Error("document is not focused");
		},
	};
	await plugin.__internals.copyToClipboard("x", clipboard);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/page.test.mjs"`
Expected: FAIL — `TypeError: copyToClipboard is not a function`

- [ ] **Step 3: 写实现**

**先删掉 Task 1 留下的两个占位组件**（`GalleryIcon` 与 `GalleryPage`）：它们各自会被下面新增的 `IconCell` 与新 `GalleryPage` 取代，留着就是同一作用域里的重复函数声明。

在 `lib/client.js` 的 `galleryView` 之后插入：

```js
		function copyToClipboard(text, clipboard = globalThis.navigator?.clipboard) {
			if (clipboard === undefined || typeof clipboard.writeText !== "function") return;
			return clipboard.writeText(String(text)).catch(() => {});
		}

		/** The sidebar icon cell: the only prop the owner passes is its geometry. */
		function IconCell({ size, active }) {
			return galleryIcon({ size, active });
		}

		/**
		 * The panel: hook wiring around `galleryView`, nothing else.
		 *
		 * Every decision the panel makes is in `galleryView`; this function only moves
		 * state in and out of React, which is why it is the shortest part of the file.
		 */
		function GalleryPage() {
			const [state, setState] = react.useState({
				phase: "loading",
				runs: [],
				selected: null,
				error: null,
				query: "",
				tool: "",
				sort: "newest",
				includeFailed: false,
			});

			const load = react.useCallback(async () => {
				setState((prev) => ({ ...prev, phase: "loading", error: null }));
				try {
					const { runs } = await loadIndex();
					setState((prev) => ({
						...prev,
						phase: runs.length === 0 ? "empty" : "ready",
						runs,
						error: null,
					}));
				} catch (error) {
					setState((prev) => ({
						...prev,
						phase: "error",
						error: error?.message ?? String(error),
					}));
				}
			}, []);

			react.useEffect(() => {
				load();
			}, [load]);

			const visible = sortRuns(
				filterRuns(state.runs, {
					query: state.query,
					tool: state.tool,
					includeFailed: state.includeFailed,
				}),
				state.sort
			);

			const actions = {
				refresh: load,
				select: (runId) => setState((prev) => ({ ...prev, selected: runId })),
				back: () => setState((prev) => ({ ...prev, selected: null })),
				copyPath: (path) => copyToClipboard(path),
				setQuery: (query) => setState((prev) => ({ ...prev, query })),
				setTool: (tool) => setState((prev) => ({ ...prev, tool })),
				setSort: (sort) => setState((prev) => ({ ...prev, sort })),
				setIncludeFailed: (includeFailed) => setState((prev) => ({ ...prev, includeFailed })),
			};

			return galleryView({ ...state, runs: visible }, actions);
		}
```

把 `apply` 里注册 `GalleryIcon` 换成 `IconCell`，并把 `copyToClipboard` / `IconCell` / `GalleryPage` 补进 `__internals`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/*.test.mjs"`
Expected: PASS（38 + 4 passed）

- [ ] **Step 5: 提交**

```bash
git add dsh-manim-gallery
git commit -m "feat(manim-gallery): React 接线（加载/刷新/筛选/复制）"
```

---

## Task 5: 样式与主题

**Files:**
- Modify: `dsh-manim-gallery/lib/client.js`
- Test: `dsh-manim-gallery/test/style.test.mjs`

- [ ] **Step 1: 写失败测试**

`dsh-manim-gallery/test/style.test.mjs`:

```js
import assert from "node:assert/strict";
import { test } from "node:test";

import { loadClient } from "./harness.mjs";

const { plugin } = loadClient();
const { STYLE_ID, GALLERY_CSS, ensureStyle } = plugin.__internals;

test("the stylesheet is namespaced so it cannot leak into the shell", () => {
	assert.equal(STYLE_ID, "@dsh-manim-gallery/panel.css");
	assert.ok(GALLERY_CSS.includes(".manim-gallery"));
});

test("every colour comes from a theme token, not a literal", () => {
	const literals = GALLERY_CSS.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
	assert.deepEqual(literals, [], `hard-coded colours: ${literals.join(", ")}`);
	assert.ok(GALLERY_CSS.includes("var(--dsw-"));
});

test("ensureStyle injects the sheet once and reuses the tag afterwards", () => {
	const appended = [];
	globalThis.document = {
		querySelector: () => (appended.length > 0 ? { tagName: "STYLE" } : null),
		createElement: () => ({ dataset: {}, textContent: "" }),
		head: { appendChild: (tag) => appended.push(tag) },
	};
	ensureStyle();
	assert.equal(appended.length, 1);
	assert.equal(appended[0].dataset.pluginCss, STYLE_ID);

	ensureStyle();
	assert.equal(appended.length, 1, "a second call must not inject a second sheet");
	delete globalThis.document;
});

test("ensureStyle is a no-op without a document", () => {
	delete globalThis.document;
	assert.doesNotThrow(() => ensureStyle());
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/style.test.mjs"`
Expected: FAIL — `TypeError: ensureStyle is not a function`

- [ ] **Step 3: 写实现**

在 `lib/client.js` 顶部（`PANEL_ID` 之前）插入：

```js
		const STYLE_ID = "@dsh-manim-gallery/panel.css";

		/**
		 * Colours are theme tokens only. A literal here would survive a switch to the
		 * light theme and paint dark-on-dark, which is exactly the failure mode the
		 * `--dsw-*` vocabulary exists to prevent.
		 */
		const GALLERY_CSS = `
.manim-gallery { display: flex; flex-direction: column; gap: 16px; padding: 20px 24px; height: 100%; overflow: auto; color: var(--dsw-alias-label-primary); }
.manim-gallery__glyph { display: block; }
.manim-gallery__glyph.is-active { color: var(--dsw-alias-label-primary); }
.manim-gallery__toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.manim-gallery__search, .manim-gallery__select { background: var(--dsw-alias-bg-base); color: inherit; border: 1px solid var(--dsw-alias-border-l2); border-radius: 6px; padding: 6px 10px; font: inherit; }
.manim-gallery__search { min-width: 220px; }
.manim-gallery__button { background: var(--dsw-alias-interactive-bg-hover); color: inherit; border: 1px solid var(--dsw-alias-border-l2); border-radius: 6px; padding: 6px 12px; font: inherit; cursor: pointer; }
.manim-gallery__button:hover { background: var(--dsw-alias-interactive-bg-active); }
.manim-gallery__toggle { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; }
.manim-gallery__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.manim-gallery__card { display: flex; flex-direction: column; gap: 8px; padding: 10px; text-align: left; background: var(--dsw-alias-bg-base); color: inherit; border: 1px solid var(--dsw-alias-border-l2); border-radius: 10px; cursor: pointer; font: inherit; }
.manim-gallery__card:hover { border-color: var(--dsw-alias-label-primary); }
.manim-gallery__thumb { width: 100%; aspect-ratio: 16 / 9; object-fit: contain; background: var(--dsw-alias-bg-base); border-radius: 6px; }
.manim-gallery__thumb.is-missing, .manim-gallery__player.is-missing { display: flex; align-items: center; justify-content: center; color: var(--dsw-alias-label-tertiary); font-size: 13px; }
.manim-gallery__cardTitle { font-size: 14px; font-weight: 600; }
.manim-gallery__cardMeta { font-size: 12px; color: var(--dsw-alias-label-tertiary); }
.manim-gallery__cardMeta .is-failed { color: var(--dsw-alias-label-error, inherit); }
.manim-gallery__detail { display: flex; flex-direction: column; gap: 16px; }
.manim-gallery__detailBar { display: flex; gap: 12px; align-items: center; }
.manim-gallery__detailTitle { font-size: 16px; margin: 0; flex: 1; }
.manim-gallery__player { width: 100%; max-height: 60vh; background: var(--dsw-alias-bg-base); border-radius: 8px; }
.manim-gallery__facts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 0; font-size: 13px; }
.manim-gallery__facts dt { color: var(--dsw-alias-label-tertiary); }
.manim-gallery__facts dd { margin: 0; overflow-wrap: anywhere; }
.manim-gallery__error { color: var(--dsw-alias-label-error, inherit); }
.manim-gallery__hint { color: var(--dsw-alias-label-tertiary); font-size: 13px; }
`;

		function ensureStyle() {
			const doc = globalThis.document;
			if (doc === undefined) return;
			if (doc.querySelector(`style[data-plugin-css="${STYLE_ID}"]`) !== null) return;
			const tag = doc.createElement("style");
			tag.dataset.plugin = "dsh-manim-gallery";
			tag.dataset.pluginCss = STYLE_ID;
			tag.textContent = GALLERY_CSS;
			doc.head.appendChild(tag);
		}
```

把 `ensureStyle()` 加进 `apply` 的第一行，并把 `STYLE_ID` / `GALLERY_CSS` / `ensureStyle` 补进 `__internals`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\myprogram\dshplugin\dsh-manim-gallery; node --test "test/*.test.mjs"`
Expected: PASS（42 + 4 passed）

- [ ] **Step 5: 提交**

```bash
git add dsh-manim-gallery
git commit -m "feat(manim-gallery): 面板样式（全部走 --dsw-* 主题 token）"
```

---

## Task 6: README 与只读边界

**Files:**
- Create: `dsh-manim-gallery/README.md`

- [ ] **Step 1: 写 README**

`dsh-manim-gallery/README.md` 必须包含：

1. 一句话定位：本组件属于 `D:\myprogram\dshplugin` 的哪一部分，它消费谁的数据（`manim-mcp` 写的 `renders/index.json`）。
2. **加载方式**：`package.json` 的 `dsh.bundle.patch` / `dsh.client` 各是什么作用；`cordis.patch.yml` 的 insert 行；以及「必须同时把包名加进 profile 的 `dsh.profile.bundles` 并建 `node_modules` 链接」。
3. **数据通路图**：`index.json` → `fetch /api/file` → `<img>`/`<video>` → `/api/file`。写明鉴权由页面的 `dsh-auth-*` cookie 自动携带，**裸请求会 401**。
4. **`RENDER_ROOT` 由 install.ps1 改写**：指出 `lib/client.js` 里那一行与其形状约定。
5. **只读边界（必须写清楚，这是有意的设计决定）**：面板不做删除、不做重渲染。原因是手写打包插件没有 client→host 调用通道（client→host 走 Typert Gateway 生成的 Remote 贡献，需要完整 TS 构建管线），所以任何写操作改由 MCP 侧的 `runs` 工具承担。面板只提供「复制路径」。
6. **排错**：面板不出现 → 检查 profile 的 bundles 与 `node_modules` 链接；面板显示「读不到动画库」→ 检查 `RENDER_ROOT` 与 `index.json` 是否存在；缩略图空白 → 用浏览器直接打开打印出的 `/api/file?path=…` 看是否 401。
7. **测试**：`node --test "test/*.test.mjs"` 的作用与它 mock 了什么。

- [ ] **Step 2: 提交**

```bash
git add dsh-manim-gallery/README.md
git commit -m "docs(manim-gallery): 组件说明、数据通路与只读边界"
```

---

## 执行期间的偏离记录

按 TDD 执行时发现计划本身的问题，已就地修正。**这些修正优先于上方对应步骤的原文。**

| # | 任务 | 计划原文的问题 | 实际采用的修正 |
|---|---|---|---|
| 1 | 全部 | `node --test test/`（带尾斜杠）在 **Node 22 下被当成模块路径**，报 `Cannot find module '...\test'`；四种写法实测只有 glob 与显式文件可用 | 全部改为 `node --test "test/*.test.mjs"`（已验证），`package.json` 的 test 脚本同步改 |
| 2 | Task 3 | `test("the detail view offers a way back and a way to copy the path")` 断言 `el.props.onClick === acts.copyPath`。但详情页的复制按钮是 `() => actions.copyPath(target)` 这个**箭头包装**，与 `acts.copyPath` 永不相等（实现错：测试写错了比较对象） | 复制按钮加独立的 `manim-gallery__copy` 类名，测试按类名找到它、**调用它**、再断言 `copyPath` 收到了 MP4 路径——比原来的身份比较更强 |
| 3 | Task 3 | `test("the detail view shows the metadata a reader would ask for")` 断言正文含 `/equation/`，但元信息里只渲染了**中文标签**「公式推导」（`TOOL_LABELS` 映射后），原始工具名 `equation` 从未出现 | 详情页增加一项 `fact("工具", run.tool)`（原始 id 对排查也有用），两种形式都断言 |
| 4 | Task 4 | `react.useEffect(() => { load(); })` 不返回 promise，所以 `await effect.fn()` **在 fetch 完成前就返回**，三条断言全部读到 `phase: "loading"`。而 effect 也不能返回那个 promise——React 会把返回值当成清理函数 | 把加载状态机抽成独立的 `loadInto(setState)`（与 `galleryView` 同样的分解思路）；测试用**自己的 recorder** 直接 await 它，另有一条测试证明 effect 确实启动了加载 |
| 5 | Task 3 / 4 | 计划把 Task 3 与 Task 4 安排为两次提交 | 实际合并为一次（`40f8bca`）。视图层与接线在同一文件里交替改动，拆开会让中间提交短暂不可用 |
| 6 | Task 5 | 计划给了 4 条样式测试 | 增加第 5 条 `apply injects the stylesheet`：前 4 条只测 `ensureStyle` 自己，没有一条证明 `apply` 真的调了它 |
| 7 | 后续需求（右侧栏） | 计划只把面板挂在左侧栏。用户要求「动画要能显示到右侧的文件预览区」，于是用 `ctx.get("sidebarRight")` 取服务——**恒为 `undefined`**：`ctx.get` 会跨越插件作用域边界，取不到由别的插件提供的服务 | 改为与官方插件同构的写法：`exports.inject = ["slots","sidebarRight","layout"]`，然后读 `ctx.sidebarRight` / `ctx.layout`。依据是 shipped 的 `dsh-client-ui-sidebar-files` 正是 `inject` 后直接读属性 |
| 8 | 后续需求（右侧栏） | `sidebarRight.controller.openResource()` 在右列的座位挂载完成前会**抛** `"sidebarRight: no session surface is mounted"`，而挂载时机与插件 `apply` 的相对顺序不保证 | `openInRightbar` 改为重试循环（40 × 50ms），全部失败才 warn。**不静默**：失败路径留下明确日志 |
| 9 | 后续需求（右侧栏） | `fileUrl` 给绝对路径**加了前导斜杠**，发出的 `path` 形如 `/D:/...`，Host 解析成 `C:\D:\...` → 面板里每张图 404 | 去掉前导斜杠，原样发送 `D:/...`。用户确认「成功了」。与引擎侧第 20 条偏离**同源同因**：同一个 `path.resolve` 语义在两个组件里各咬了一次 |
| 10 | 后续需求（右侧栏） | `makeGalleryPage` 在签名改为接收已解析的 `services` 之后，函数体内仍留着 `ctx.get(...)`，渲染期抛 `ctx.get is not a function` | 改为完全从传入的 `services` 取值；新增测试钉死「页面构造期不触碰 ctx」 |
| 11 | 后续需求（入口位置） | 用户反馈「我没有看到点开之后有动画库之类的」，并要求「或者你可以把动画库放到右上角这里」 | 除左侧栏常驻图标外，再注册 `conversation.session.header.utilities`（右对齐、会话级）的「动画库」按钮作为**第二入口**；两个入口调同一个 `openGalleryPanel` |
| 12 | 后续需求（可验证性） | 客户端插件跑在浏览器里，离线测试只能覆盖纯函数，无法证明它真的挂上了槽位 | `publishProbe(services)` 把面板状态挂到 `globalThis.__DSH_MANIM_GALLERY__`，使槽位注册与右栏可用性可被外部查询验证；这是**诊断面**，不参与业务逻辑 |

**执行结果**：53 个离线测试全绿（计划预期 42 + 4 = 46，多出的 7 条来自上表第 2/3/4/6 条的修正与加强），`lib/client.js` 零硬编码颜色、零写请求。



## 完成判据

Plan 2 完成的定义：

1. `cd dsh-manim-gallery; node --test "test/*.test.mjs"` 全绿，0 failed。
2. `lib/client.js` 里没有一行硬编码颜色（只有 `--dsw-*` token）。
3. 离线 harness 能证明：模块以 `dsh-manim-gallery` 注册、`inject` 只要 `slots`、`apply` 注册了 `sidebar.panellist{id:"manim-gallery"}` 与 `main{key:"manim-gallery"}`。
4. `galleryView` 的四种状态（loading/empty/error/ready）与详情视图都有断言覆盖。
5. 详情视图渲染 `<video controls>`，其 `src` 指向 `/api/file?path=…mp4`。
6. README 说明了只读边界及其技术原因。

**本计划不覆盖**（属于 Plan 3 或后续）：

- 把插件装进 `~/.dsh/profiles/web`（改 `package.json`、`pnpm install`、重启 web）——Plan 3。
- 在真实浏览器里看到面板——Plan 3 的端到端验收。
- MCP 侧 `runs action=delete`——后续任务，不在 Plan 2 范围。
- 面板内重渲染与导出——v2。
