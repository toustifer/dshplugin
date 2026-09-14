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

		exports.__internals = { TOOL_KEY, readEnvelope, readMedia };
		exports.apply = function apply() {
			throw new Error("apply is added by Task 11");
		};
		return module.exports;
	},
});
