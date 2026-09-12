import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, loadClient } from "./harness.mjs";

test("the module registers itself under the package name", () => {
	const { entry } = loadClient();
	assert.equal(entry.id, "dsh-manim-gallery");
	assert.equal(typeof entry.factory, "function");
});

test("the plugin declares the services it reaches as context properties", () => {
	const { plugin } = loadClient();
	// `sidebarRight` and `layout` are reached as `ctx.sidebarRight` / `ctx.layout`,
	// which is only legal for a DECLARED dependency. The shipped plugins do the same
	// (`dsh-client-ui-sidebar-files` injects `sidebarRightTabs` and then uses
	// `ctx.sidebarRightTabs`); probing with `ctx.get` crosses a scope boundary and
	// silently yields undefined — which is how the first version lost the button.
	assert.deepEqual(plugin.inject, ["slots", "sidebarRight", "layout"]);
	assert.equal(typeof plugin.apply, "function");
});

test("apply registers the panel icon, the matching main panel, and a header entry", () => {
	const { plugin } = loadClient();
	const { ctx, registrations } = createCtx();
	plugin.apply(ctx);

	assert.equal(registrations.length, 3);

	const icon = registrations.find((r) => r.options.name === "sidebar.panellist");
	const page = registrations.find((r) => r.options.name === "main");
	const header = registrations.find(
		(r) => r.options.name === "conversation.session.header.utilities"
	);
	assert.ok(icon, "sidebar.panellist was not registered");
	assert.ok(page, "main was not registered");
	assert.ok(header, "the header entry was not registered");

	// The sidebar resolves the button from list metadata, and that same id is what
	// the layout dispatches into `main` — the two must be one string.
	assert.equal(icon.options.id, "manim-gallery");
	assert.equal(page.options.key, "manim-gallery");
	assert.equal(icon.options.label, "动画库");
	assert.ok(Number.isFinite(icon.options.order));

	// The header entry is a second door to the same panel, so it carries the same id
	// and a label the owner can project.
	assert.equal(header.options.id, "manim-gallery");
	assert.equal(header.options.label, "动画库");
	assert.ok(Number.isFinite(header.options.order));
});
