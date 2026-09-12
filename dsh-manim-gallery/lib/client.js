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
	},
});
