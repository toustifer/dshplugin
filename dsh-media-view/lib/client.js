/**
 * The conversation-side renderer for `mcp__media__publish_file`.
 *
 * Why a tool view and not the assistant's own text: the assistant body is rendered by
 * the shipped `assistant-step` node, and replacing it would mean reimplementing all of
 * Markdown. `tool.call.toolview` is keyed by tool name, its key domain is open, and an
 * unclaimed key falls back to the generic tool row — so registering our own tool's key
 * is additive and shadows nothing.
 *
 * The key is a literal and a typo never renders (no error, no fallback notice), so
 * `test/register.test.mjs` asserts it character for character.
 */
window.__ModuleLoader__.load({
	id: "dsh-media-view",
	factory: (require) => {
		const module = { exports: {} };
		const exports = module.exports;

		const react = require("react");
		const h = react.createElement;

		const TOOL_KEY = "mcp__media__publish_file";

		/** Pull our JSON envelope out of a settled tool result. Never throws. */
		function readEnvelope(block) {
			const content = block?.content;
			if (!Array.isArray(content)) return null;
			for (const item of content) {
				if (item?.type !== "text" || typeof item.text !== "string") continue;
				const trimmed = item.text.trim();
				if (!trimmed.startsWith("{")) continue;
				try {
					const parsed = JSON.parse(trimmed);
					if (parsed && typeof parsed === "object") return parsed;
				} catch {
					// Not ours, or truncated: keep looking, then give up quietly.
				}
			}
			return null;
		}

		/** A descriptor we can actually render, or null. */
		function readMedia(envelope) {
			if (!envelope || envelope.ok !== true) return null;
			const media = envelope.media;
			if (!media || typeof media !== "object") return null;
			if (typeof media.kind !== "string" || typeof media.reference !== "string") return null;
			return media;
		}

		const STYLE_ID = "@dsh-media-view/view.css";

		/** Same-origin endpoint. `reference` is host-computed; the client only encodes. */
		function fileUrl(reference) {
			return `/api/file?path=${encodeURIComponent(reference)}`;
		}

		const MEDIA_CSS = `
.manim-media { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--dsw-alias-border-l2); border-radius: 10px; background: var(--dsw-alias-bg-base); color: var(--dsw-alias-label-primary); }
.manim-media__title { font-size: 14px; font-weight: 600; }
.manim-media__meta { font-size: 12px; color: var(--dsw-alias-label-tertiary); }
.manim-media__video, .manim-media__audio { width: 100%; border-radius: 8px; background: var(--dsw-alias-bg-base); }
.manim-media__video { max-height: 60vh; }
.manim-media__image { max-width: 100%; border-radius: 8px; }
.manim-media__pages { display: flex; flex-direction: column; gap: 8px; }
.manim-media__open { align-self: flex-start; background: var(--dsw-alias-interactive-bg-hover); color: inherit; border: 1px solid var(--dsw-alias-border-l2); border-radius: 6px; padding: 4px 10px; font: inherit; cursor: pointer; }
.manim-media__open:hover { background: var(--dsw-alias-interactive-bg-active); }
.manim-media__pending { color: var(--dsw-alias-label-tertiary); font-size: 13px; }
.manim-media__error { color: var(--dsw-alias-label-error, inherit); font-size: 13px; }
.manim-media__hint { color: var(--dsw-alias-label-tertiary); font-size: 12px; }
`;

		function ensureStyle() {
			const doc = globalThis.document;
			if (doc === undefined) return;
			if (doc.querySelector(`style[data-plugin-css="${STYLE_ID}"]`) !== null) return;
			const tag = doc.createElement("style");
			tag.dataset.plugin = "dsh-media-view";
			tag.dataset.pluginCss = STYLE_ID;
			tag.textContent = MEDIA_CSS;
			doc.head.appendChild(tag);
		}

		/**
		 * Open one file in the right column.
		 *
		 * The shipped document preview owns `dsh-resource://file/**` and renders PDFs,
		 * images, Markdown and HTML with pdf.js. `openResource` throws
		 * "no session surface is mounted" until the column's seat binds, so it is
		 * retried; giving up is reported, never silent.
		 */
		function openInRightbar(absolutePath, services = {}, options = {}) {
			const { sidebarRight } = services;
			if (sidebarRight === undefined || typeof sidebarRight.openResource !== "function") {
				return false;
			}
			const address = `dsh-resource://file/absolute/${String(absolutePath)
				.replace(/\\/g, "/")
				.replace(/%3A/gi, ":")
				.split("/")
				.filter((segment) => segment !== "")
				.map((segment) => encodeURIComponent(segment).replace(/%3A/gi, ":"))
				.join("/")}`;
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
						warn(`[dsh-media-view] 无法在右侧栏打开（已重试 ${tries} 次）：${error?.message ?? error}`);
						return false;
					}
					schedule(attempt);
					return false;
				}
			};
			attempt();
			return true;
		}

		function formatBytes(bytes) {
			if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "";
			if (bytes < 1024) return `${bytes} B`;
			if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
			return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
		}

		function shell(className, parts) {
			return h("div", { className: `manim-media ${className}` }, ...parts);
		}

		function openButton(media, services) {
			const target = media.path || media.reference;
			if (typeof target !== "string") return null;
			return h(
				"button",
				{
					className: "manim-media__open",
					type: "button",
					onClick: () => openInRightbar(target, services),
				},
				"在右侧栏打开",
			);
		}

		function renderOne(media, services, key) {
			const source = fileUrl(media.reference);
			if (media.kind === "image") {
				return h("img", { key, className: "manim-media__image", src: source, alt: media.name ?? "" });
			}
			if (media.kind === "video") {
				return h("video", { key, className: "manim-media__video", src: source, controls: true, preload: "metadata" });
			}
			if (media.kind === "audio") {
				return h("audio", { key, className: "manim-media__audio", src: source, controls: true, preload: "metadata" });
			}
			return null;
		}

		const MediaView = (props = {}) => {
			const block = props?.block ?? props;
			const services = props;
			if (block?.kind !== "tool-result") {
				return shell("is-pending", [
					h("div", { className: "manim-media__pending" }, "正在发布文件…"),
				]);
			}
			const envelope = readEnvelope(block);
			if (envelope && envelope.ok === false) {
				return shell("is-refused", [
					h("div", { className: "manim-media__error" }, `发布失败：${envelope.reason ?? "unknown"}`),
					envelope.detail ? h("div", { className: "manim-media__meta" }, envelope.detail) : null,
					envelope.hint ? h("div", { className: "manim-media__hint" }, envelope.hint) : null,
				].filter(Boolean));
			}
			const media = readMedia(envelope);
			if (media === null) {
				return shell("is-generic", [
					h("div", { className: "manim-media__meta" }, "文件已发布（结果无法解析）"),
				]);
			}
			const extras = Array.isArray(envelope.extras) ? envelope.extras : [];
			const parts = [];
			if (media.title) parts.push(h("div", { key: "t", className: "manim-media__title" }, media.title));
			const inline = renderOne(media, services, "main");
			if (inline) parts.push(inline);
			const pages = extras
				.map((extra, index) => renderOne(extra, services, `extra-${index}`))
				.filter(Boolean);
			if (pages.length > 0) {
				parts.push(h("div", { key: "pages", className: "manim-media__pages" }, ...pages));
			}
			parts.push(
				h(
					"div",
					{ key: "meta", className: "manim-media__meta" },
					[media.name, formatBytes(media.bytes), media.pages ? `共 ${media.pages} 页` : null]
						.filter(Boolean)
						.join(" · "),
				),
			);
			const button = openButton(media, services);
			if (button) parts.push(button);
			for (const warning of Array.isArray(envelope.warnings) ? envelope.warnings : []) {
				parts.push(h("div", { key: `w-${warning}`, className: "manim-media__hint" }, warning));
			}
			return shell("is-ready", parts);
		};

		exports.__internals = {
			TOOL_KEY,
			readEnvelope,
			readMedia,
			fileUrl,
			formatBytes,
			openInRightbar,
			MediaView,
		};
		exports.inject = ["slots", "sidebarRight"];
		exports.apply = function apply(ctx) {
			ensureStyle();
			const services = { sidebarRight: ctx.sidebarRight };
			ctx.slots.inject("tool.call.toolview", () =>
				ctx.slots.register({ name: "tool.call.toolview", key: TOOL_KEY }, (props) =>
					MediaView({ ...props, ...services }),
				),
			);
		};
		return module.exports;
	},
});
