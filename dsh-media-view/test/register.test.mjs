import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, loadClient } from "./harness.mjs";

const { plugin } = loadClient();

test("the registered key is character-for-character the MCP wire name", () => {
	// `mcp__<serverName>__<rawName>`. A typo here never renders and never warns —
	// the slot simply has no occupant for that tool, so nothing would catch it.
	assert.equal(plugin.__internals.TOOL_KEY, "mcp__media__publish_file");
});

test("apply registers exactly one tool view and nothing else", () => {
	const { ctx, registrations } = createCtx({ services: { sidebarRight: {} } });
	plugin.apply(ctx);
	assert.equal(registrations.length, 1);
	assert.equal(registrations[0].options.name, "tool.call.toolview");
	assert.equal(registrations[0].options.key, "mcp__media__publish_file");
	assert.equal(typeof registrations[0].component, "function");
});

test("the renderer reads services from declared properties, never ctx.get", () => {
	const { ctx, asked } = createCtx({ services: { sidebarRight: {} } });
	plugin.apply(ctx);
	assert.deepEqual(asked, [], "ctx.get crosses a scope boundary and yields undefined");
});

test("the plugin declares only the services it reaches", () => {
	assert.deepEqual(plugin.inject, ["slots", "sidebarRight"]);
});

test("apply never issues a write", () => {
	const { ctx } = createCtx({ services: { sidebarRight: {} } });
	const before = JSON.stringify(globalThis.fetch ?? null);
	plugin.apply(ctx);
	assert.equal(JSON.stringify(globalThis.fetch ?? null), before);
});
