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

test("apply registers only the main panel, and neither visible door", () => {
	// The left rail icon (`sidebar.panellist`) and the Session header button
	// (`conversation.session.header.utilities`) were removed on request once the
	// animation started arriving embedded in the answer body. This asserts the
	// absence, not just the presence: re-adding a `register` call without meaning to
	// is exactly the regression worth catching, because it puts a permanent button
	// back into every conversation.
	const { plugin } = loadClient();
	const { ctx, registrations } = createCtx();
	plugin.apply(ctx);

	assert.deepEqual(
		registrations.map((r) => r.options.name),
		["main"]
	);

	const page = registrations[0];
	assert.equal(page.options.key, "manim-gallery");
	// `main` is dispatched by the panel id, so the key must stay that literal string.
	assert.equal(typeof page.component, "function");
});

test("the removed doors still exist as tested components, ready to be re-registered", () => {
	// Removing the registrations is a UI decision, not a deletion: `IconCell` and
	// `makeHeaderButton` stay built and exercised so that restoring either door is one
	// `ctx.slots.register(...)` call.
	const { plugin } = loadClient();
	assert.equal(typeof plugin.__internals.IconCell, "function");
	assert.equal(typeof plugin.__internals.makeHeaderButton, "function");
	assert.equal(typeof plugin.__internals.openGalleryPanel, "function");
});
