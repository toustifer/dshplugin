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
.manim-gallery__header { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; padding: 0; background: none; border: none; border-radius: 6px; color: var(--dsw-alias-label-secondary); cursor: pointer; }
.manim-gallery__header:hover { background: var(--dsw-alias-interactive-bg-hover); color: var(--dsw-alias-label-primary); }
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

		/**
		 * Where manim-mcp writes its runs. `install.ps1` rewrites the string literal
		 * on the next line so the panel and the MCP always agree on one root; keep
		 * this line's shape stable or that rewrite silently stops matching.
		 */
		const RENDER_ROOT = "D:/myprogram/dshplugin/renders";
		const INDEX_PATH = `${RENDER_ROOT}/index.json`;

		/**
		 * Route one absolute Host path through DSH's authenticated file endpoint.
		 *
		 * The path is sent WITHOUT a leading slash. `/api/file` resolves it with
		 * `node:path.resolve`, and on Windows `resolve(cwd, "/D:/x")` returns
		 * `C:\D:\x` — the leading slash makes Node treat the drive letter as an
		 * ordinary path segment and glue the whole thing onto the cwd's drive, so
		 * the file is never found and the endpoint answers 404. `D:/x` resolves to
		 * `D:\x` correctly. (A 401 from this endpoint means auth; a 404 means the
		 * path form or a genuinely absent file.)
		 */
		function fileUrl(absolutePath) {
			const slashed = String(absolutePath).replace(/\\/g, "/");
			return `/api/file?path=${encodeURIComponent(slashed)}`;
		}

		function indexUrl() {
			return fileUrl(INDEX_PATH);
		}

		/**
		 * Address one absolute path as a DSH file resource.
		 *
		 * Mirrors `dsh-util-workspace-path`'s `absoluteFileAddress`: normalize the
		 * separators, drop a leading slash, then percent-encode each segment while
		 * keeping the drive colon literal. The shipped document preview registers a
		 * `dsh-resource://file/**` implementation, so this address is what lets the
		 * right sidebar open a GIF with its own viewer instead of us writing one.
		 */
		function resourceAddress(absolutePath) {
			const normalized = String(absolutePath).replace(/\\/g, "/");
			const absolute = normalized.replace(/^\/+/, "");
			const encoded = absolute
				.split("/")
				.map((segment) => encodeURIComponent(segment).replace(/%3A/gi, ":"))
				.join("/");
			return `dsh-resource://file/absolute/${encoded}`;
		}

		/**
		 * The artifact the right sidebar can actually render.
		 *
		 * Its preview lists gif/webp/png and does not list video/mp4, so the MP4 is
		 * deliberately never handed over — that would open a tab showing nothing.
		 */
		function previewablePath(run) {
			const preview = run?.assets?.preview;
			if (typeof preview === "string" && preview) return preview;
			const poster = run?.assets?.poster;
			if (typeof poster === "string" && poster) return poster;
			return null;
		}

		/**
		 * Open one artifact in the right sidebar.
		 *
		 * Two timing facts drive the shape of this function, both read out of the
		 * shipped sidebar-right client:
		 *
		 * 1. `openResource` goes through `controller.require()`, which THROWS
		 *    `"sidebarRight: no session surface is mounted"` until the column's seat
		 *    has mounted and bound the current session. Expanding the column and
		 *    calling it in the same tick therefore throws, and the click looks dead —
		 *    so the call is retried until the binding exists.
		 * 2. Whether `openResource` also reveals the column is not part of its
		 *    contract, so the column is expanded explicitly first.
		 *
		 * Giving up silently is not allowed: the button would stay there looking
		 * alive, so the last failure is reported.
		 */
		function openInRightbar(absolutePath, services = {}, options = {}) {
			const { sidebarRight, layout } = services;
			if (sidebarRight === undefined || typeof sidebarRight.openResource !== "function") {
				return false;
			}

			if (layout !== undefined && typeof layout.openRightbar === "function") {
				layout.openRightbar(true, false);
			}

			const address = resourceAddress(absolutePath);
			const attempts = options.attempts ?? 40;
			const delayMs = options.delayMs ?? 50;
			const schedule = options.schedule ?? ((fn) => globalThis.setTimeout(fn, delayMs));
			const warn = options.warn ?? ((message) => console.warn(message));
			let tries = 0;

			const attempt = () => {
				tries += 1;
				try {
					sidebarRight.openResource(address);
					return true;
				} catch (error) {
					if (tries >= attempts) {
						warn(
							`[manim-gallery] 无法在右侧栏打开动画（已重试 ${tries} 次）：${error?.message ?? error}`
						);
						return false;
					}
					schedule(attempt);
					return false;
				}
			};

			attempt();
			return true;
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
			const previewable = previewablePath(run);
			// Offered only when the panel can actually do it: no `sidebarRight` service,
			// or nothing the shipped preview can render, means no button rather than a
			// button that does nothing.
			const canOpenInRightbar =
				typeof actions.openInRightbar === "function" && previewable !== null;
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
					canOpenInRightbar
						? h(
								"button",
								{
									className: "manim-gallery__button manim-gallery__rightbar",
									type: "button",
									onClick: () => actions.openInRightbar(previewable),
								},
								"在右侧打开"
							)
						: null,
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

		const INITIAL_STATE = {
			phase: "loading",
			runs: [],
			selected: null,
			error: null,
			query: "",
			tool: "",
			sort: "newest",
			includeFailed: false,
		};

		/**
		 * Every action the view can dispatch, as a function of the state setter and
		 * the resolved Client services.
		 *
		 * Built as a plain factory rather than inline so "the right-sidebar action
		 * exists only when the service does" is an assertable fact instead of a
		 * property of a rendered tree nobody can reach in a test.
		 */
		function galleryActions({ setState, services = {} }) {
			const actions = {
				refresh: () => loadInto(setState),
				select: (runId) => setState((prev) => ({ ...prev, selected: runId })),
				back: () => setState((prev) => ({ ...prev, selected: null })),
				copyPath: (path) => copyToClipboard(path),
				setQuery: (query) => setState((prev) => ({ ...prev, query })),
				setTool: (tool) => setState((prev) => ({ ...prev, tool })),
				setSort: (sort) => setState((prev) => ({ ...prev, sort })),
				setIncludeFailed: (includeFailed) => setState((prev) => ({ ...prev, includeFailed })),
			};
			if (services.sidebarRight !== undefined) {
				actions.openInRightbar = (path) => openInRightbar(path, services);
			}
			return actions;
		}

		/**
		 * The panel component: React wiring only.
		 *
		 * The services arrive already resolved. They are declared dependencies, so
		 * Cordis guarantees they exist by the time `apply` runs — the earlier attempt
		 * to look them up per render with `ctx.get` was not only unnecessary, it was
		 * the bug: a sibling plugin's service is not visible that way.
		 */
		function makeGalleryPage(services) {
			return function GalleryPage() {
				const [state, setState] = react.useState(INITIAL_STATE);

				react.useEffect(() => {
					loadInto(setState);
				}, []);

				const actions = galleryActions({ setState, services });
				const visible = sortRuns(
					filterRuns(state.runs, {
						query: state.query,
						tool: state.tool,
						includeFailed: state.includeFailed,
					}),
					state.sort
				);

				return galleryView({ ...state, runs: visible }, actions);
			};
		}

		/** The header entry's cell: an icon-only button, like its neighbours. */
		function makeHeaderButton(services) {
			return function GalleryHeaderButton() {
				return h(
					"button",
					{
						className: "manim-gallery__header",
						type: "button",
						title: "动画库",
						"aria-label": "动画库",
						onClick: () => openGalleryPanel(services),
					},
					galleryIcon({ size: 16, active: false })
				);
			};
		}

		/** Reveal the gallery panel in the main column. */
		function openGalleryPanel(services = {}) {
			const { layout } = services;
			if (layout === undefined || typeof layout.selectPanel !== "function") return false;
			layout.selectPanel(PANEL_ID);
			return true;
		}

		/**
		 * A console probe, in the same spirit as `dsh-cross-session-modal`'s
		 * `__DSH_XMODAL__`: when a panel misbehaves inside a browser this process
		 * cannot see, "what did the plugin actually get?" has to be measurable rather
		 * than guessed at.
		 *
		 * `__DSH_MANIM_GALLERY__.services()` answers whether the two declared
		 * dependencies arrived; `.show()` and `.open(path)` drive the two doors.
		 */
		function publishProbe(services) {
			globalThis.__DSH_MANIM_GALLERY__ = {
				panelId: PANEL_ID,
				renderRoot: RENDER_ROOT,
				services: () => ({
					layout: services.layout !== undefined,
					sidebarRight: services.sidebarRight !== undefined,
				}),
				show: () => openGalleryPanel(services),
				open: (absolutePath) => openInRightbar(absolutePath, services),
				resourceAddress,
			};
		}

		function apply(ctx) {
			ensureStyle();
			const services = { layout: ctx.layout, sidebarRight: ctx.sidebarRight };
			publishProbe(services);

			ctx.slots.inject("sidebar.panellist", () =>
				ctx.slots.register(
					{ name: "sidebar.panellist", id: PANEL_ID, order: 40, label: "动画库" },
					IconCell
				)
			);
			ctx.slots.inject("main", () =>
				ctx.slots.register({ name: "main", key: PANEL_ID }, makeGalleryPage(services))
			);
			// A second door, in the Session header's right-aligned utilities beside the
			// shipped ones: the sidebar entry is the discoverable one, and this is the
			// one that stays in sight while reading an answer.
			ctx.slots.inject("conversation.session.header.utilities", () =>
				ctx.slots.register(
					{
						name: "conversation.session.header.utilities",
						id: PANEL_ID,
						order: 10,
						label: "动画库",
					},
					makeHeaderButton(services)
				)
			);
		}

		exports.apply = apply;
		// `sidebarRight` and `layout` are DECLARED and then read as `ctx.sidebarRight` /
		// `ctx.layout`. Reaching a sibling plugin's service with `ctx.get` crosses a
		// scope boundary and yields undefined, which silently cost this plugin its
		// right-sidebar button; declaring them is what the shipped plugins do too.
		exports.inject = ["slots", "sidebarRight", "layout"];
		exports.__internals = {
			PANEL_ID,
			RENDER_ROOT,
			INDEX_PATH,
			TOOL_LABELS,
			STYLE_ID,
			GALLERY_CSS,
			ensureStyle,
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
			makeGalleryPage,
			makeHeaderButton,
			openGalleryPanel,
			galleryActions,
			resourceAddress,
			previewablePath,
			openInRightbar,
			loadInto,
		};
		return module.exports;
	},
});
