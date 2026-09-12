import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, createTabRegistry, loadClient } from "./harness.mjs";

/** The declared services, mounted the way the harness mounts any dependency. */
function services(overrides = {}) {
	return { sidebarRight: {}, sidebarRightTabs: createTabRegistry(), ...overrides };
}

test("the module registers itself under the package name", () => {
	const { entry } = loadClient();
	assert.equal(entry.id, "dsh-manim-gallery");
	assert.equal(typeof entry.factory, "function");
});

test("the plugin declares the services it reaches as context properties", () => {
	const { plugin } = loadClient();
	// `sidebarRight` and `sidebarRightTabs` are reached as `ctx.sidebarRight` /
	// `ctx.sidebarRightTabs`, which is only legal for a DECLARED dependency. The shipped
	// plugins do exactly this (`dsh-client-ui-sidebar-files` injects `sidebarRightTabs`
	// and then uses `ctx.sidebarRightTabs`); probing with `ctx.get` crosses a scope
	// boundary and silently yields undefined — which is how the first version lost the
	// button.
	assert.deepEqual(plugin.inject, ["slots", "sidebarRight", "sidebarRightTabs"]);
	assert.equal(typeof plugin.apply, "function");
});

test("the plugin registers its tab type, and does so before any slot exists", () => {
	// The type is registered through `ctx.effect`, not from inside the body's `inject`
	// callback: `openTab` throws when a kind has nothing registered, and the header
	// button can be pressed before the right column's seat has mounted its body slot.
	// A registry that only fills in once the slot appears would make that click throw.
	const { plugin } = loadClient();
	const tabs = createTabRegistry();
	const { ctx } = createCtx({ services: services({ sidebarRightTabs: tabs }) });
	plugin.apply(ctx);

	assert.equal(tabs.types.length, 1);
	const definition = tabs.types[0];
	assert.equal(definition.kind, "manim-gallery");
	assert.equal(definition.id, "dsh-manim-gallery");
	// A PAGE type: it recognizes no resource address, so it must name no `patterns`.
	// Naming one would silently turn it into a resource viewer that never claims
	// anything, and `openTab` would then have no page type to open.
	assert.equal(definition.patterns, undefined);
	assert.equal(typeof definition.title, "function");
});

test("the tab type contributes no guide entry", () => {
	// The default page depends on how many guide entries are registered: exactly one
	// opens it directly (Files, in the shipped composition), zero or several open the
	// guide page instead. Contributing an entry would change what every user sees on
	// first expanding the column — a product behaviour changed by a plugin that has
	// nothing to do with it.
	const { plugin } = loadClient();
	const tabs = createTabRegistry();
	const { ctx } = createCtx({ services: services({ sidebarRightTabs: tabs }) });
	plugin.apply(ctx);

	assert.equal(tabs.types[0].guide, undefined);
});

test("apply registers the tab body and the header door, and never the left rail", () => {
	// `sidebar.panellist` (the left rail icon) is deliberately absent: the user asked
	// to keep only the top-right door. This asserts the absence, not just the presence,
	// because re-adding a register call by accident puts a permanent icon back into
	// every session's rail.
	const { plugin } = loadClient();
	const { ctx, registrations } = createCtx({ services: services() });
	plugin.apply(ctx);

	assert.deepEqual(
		registrations.map((r) => r.options.name),
		["sidebar.right.pane.tab", "conversation.session.header.utilities"]
	);
	assert.equal(
		registrations.some((r) => r.options.name === "sidebar.panellist"),
		false,
		"the left rail entry must stay removed"
	);
	assert.equal(
		registrations.some((r) => r.options.name === "main"),
		false,
		"the full-page panel must stay removed"
	);
});

test("the tab body is keyed by the type's own id", () => {
	// The seat dispatches a body by the id of the type in force, so these two strings
	// being equal is the whole contract between the registry and the slot.
	const { plugin } = loadClient();
	const tabs = createTabRegistry();
	const { ctx, registrations } = createCtx({ services: services({ sidebarRightTabs: tabs }) });
	plugin.apply(ctx);

	const body = registrations.find((r) => r.options.name === "sidebar.right.pane.tab");
	assert.equal(body.options.key, tabs.types[0].id);
	assert.equal(typeof body.component, "function");
});

test("the header door carries an id and a label the owner can project", () => {
	const { plugin } = loadClient();
	const { ctx, registrations } = createCtx({ services: services() });
	plugin.apply(ctx);

	const header = registrations.find(
		(r) => r.options.name === "conversation.session.header.utilities"
	);
	assert.equal(header.options.id, "dsh-manim-gallery");
	assert.equal(header.options.label, "动画库");
	assert.ok(Number.isFinite(header.options.order));
});
