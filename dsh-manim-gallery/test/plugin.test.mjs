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
