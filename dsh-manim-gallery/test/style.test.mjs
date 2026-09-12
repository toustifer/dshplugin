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

test("apply injects the stylesheet", () => {
	const loaded = loadClient();
	const appended = [];
	globalThis.document = {
		querySelector: () => null,
		createElement: () => ({ dataset: {}, textContent: "" }),
		head: { appendChild: (tag) => appended.push(tag) },
	};
	loaded.plugin.apply({
		slots: { inject: (key, cb) => cb(), register: () => () => {} },
		// The tab type registers through `ctx.effect`; a bare no-op is enough here,
		// because this test only asks whether the stylesheet reached the document.
		effect: (cb) => cb(),
		sidebarRight: {},
		sidebarRightTabs: { register: () => () => {} },
		get: () => undefined,
		on: () => () => {},
	});
	delete globalThis.document;
	assert.equal(appended.length, 1);
});
