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

		function round1(value) {
			return Math.round(Number(value) * 10) / 10;
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

		function fact(term, value) {
			return [h("dt", { key: `${term}-t` }, term), h("dd", { key: `${term}-d` }, String(value))];
		}

		function detail(run, actions) {
			const mp4 = run?.assets?.mp4;
			const preview = runPreviewUrl(run);
			const poster = run?.assets?.poster;
			const copyTarget = mp4 ?? run?.assets?.preview ?? "";
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
							className: "manim-gallery__button manim-gallery__copy",
							type: "button",
							onClick: () => actions.copyPath(copyTarget),
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
					fact("工具", run.tool ?? "—"),
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
				h(
					"div",
					{ className: "manim-gallery__grid", key: "grid" },
					...runs.map((run) => card(run, actions))
				)
			);
		}

		function copyToClipboard(text, clipboard = globalThis.navigator?.clipboard) {
			if (clipboard === undefined || typeof clipboard.writeText !== "function") return;
			return clipboard.writeText(String(text)).catch(() => {});
		}

		/** The sidebar icon cell: the only props the owner passes are its geometry. */
		function IconCell({ size, active }) {
			return galleryIcon({ size, active });
		}

		/**
		 * The load state machine, independent of React.
		 *
		 * It takes a `setState` rather than returning one so a test can drive it with
		 * its own recorder and await its real completion. An effect callback cannot
		 * hand back this promise — React treats a returned value as the cleanup
		 * function — so keeping the machine separate is what makes "did it end in
		 * `ready`?" an assertable question.
		 */
		async function loadInto(setState) {
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
		}

		/**
		 * The panel: hook wiring around `galleryView`, nothing else.
		 *
		 * Every decision the panel makes lives in `galleryView`; this function only
		 * moves state in and out of React, which is why it is the shortest part of
		 * the file.
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

			const load = react.useCallback(() => loadInto(setState), []);

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

		function apply(ctx) {
			ctx.slots.inject("sidebar.panellist", () =>
				ctx.slots.register(
					{ name: "sidebar.panellist", id: PANEL_ID, order: 40, label: "动画库" },
					IconCell
				)
			);
			ctx.slots.inject("main", () =>
				ctx.slots.register({ name: "main", key: PANEL_ID }, GalleryPage)
			);
		}

		exports.apply = apply;
		exports.inject = ["slots"];
		exports.__internals = {
			PANEL_ID,
			RENDER_ROOT,
			INDEX_PATH,
			TOOL_LABELS,
			fileUrl,
			indexUrl,
			relativeTime,
			runTool,
			runTitle,
			runPreviewUrl,
			sortRuns,
			filterRuns,
			loadIndex,
			galleryIcon,
			galleryView,
			copyToClipboard,
			IconCell,
			GalleryPage,
			loadInto,
		};
		return module.exports;
	},
});
