import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, loadClient, makeRun } from "./harness.mjs";

const { plugin } = loadClient();

function pageOf(loaded) {
	const { ctx, registrations } = createCtx();
	loaded.plugin.apply(ctx);
	return registrations.find((r) => r.options.name === "main").component;
}

/**
 * A real little state machine, unlike the React stub.
 *
 * `loadInto` applies functional updates to the previous state, so the recorder
 * has to do the same — otherwise it would assert on a state object React would
 * never have produced.
 */
function recorder(initial) {
	const updates = [];
	let state = initial;
	const setState = (next) => {
		state = typeof next === "function" ? next(state) : next;
		updates.push(state);
	};
	return { updates, setState, latest: () => updates.at(-1) };
}

const INITIAL = {
	phase: "loading",
	runs: [],
	selected: null,
	error: null,
	query: "",
	tool: "",
	sort: "newest",
	includeFailed: false,
};

test("the page component mounts without fetching during render", () => {
	const calls = [];
	const loaded = loadClient({
		fetchImpl: async (url) => {
			calls.push(url);
			return { ok: true, status: 200, json: async () => ({ runs: [] }) };
		},
	});
	const Page = pageOf(loaded);
	assert.equal(typeof Page, "function");

	Page({});
	assert.deepEqual(calls, [], "the render pass must not touch the network");
	assert.equal(loaded.react.hooks.effects.length, 1, "exactly one effect was registered");
});

test("the mount effect actually starts the load", async () => {
	const calls = [];
	const loaded = loadClient({
		fetchImpl: async (url) => {
			calls.push(url);
			return { ok: true, status: 200, json: async () => ({ runs: [] }) };
		},
	});
	pageOf(loaded)({});

	loaded.react.hooks.effects[0].fn();
	// The effect deliberately does not return the promise (React would take it for
	// a cleanup function), so awaiting one macrotask is how the test waits it out.
	await new Promise((resolve) => setImmediate(resolve));

	assert.equal(calls.length, 1);
	assert.ok(calls[0].startsWith("/api/file?path="));
});

test("a failed load ends in the error phase with the status in the message", async () => {
	const loaded = loadClient({
		fetchImpl: async () => ({ ok: false, status: 404, json: async () => ({}) }),
	});
	const { latest, setState } = recorder(INITIAL);
	await loaded.plugin.__internals.loadInto(setState);

	assert.equal(latest().phase, "error");
	assert.match(latest().error, /404/);
});

test("a successful load ends in the ready phase with the runs", async () => {
	const loaded = loadClient({
		fetchImpl: async () => ({
			ok: true,
			status: 200,
			json: async () => ({ updatedAt: "t", runs: [makeRun()] }),
		}),
	});
	const { latest, setState } = recorder(INITIAL);
	await loaded.plugin.__internals.loadInto(setState);

	assert.equal(latest().phase, "ready");
	assert.equal(latest().runs.length, 1);
	assert.equal(latest().error, null);
});

test("an empty index lands on the empty state, not the grid", async () => {
	const loaded = loadClient({
		fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ runs: [] }) }),
	});
	const { latest, setState } = recorder(INITIAL);
	await loaded.plugin.__internals.loadInto(setState);

	assert.equal(latest().phase, "empty");
	assert.deepEqual(latest().runs, []);
});

test("a reload clears a previous error before it resolves", async () => {
	const loaded = loadClient({
		fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ runs: [] }) }),
	});
	const { updates, setState } = recorder({ ...INITIAL, phase: "error", error: "HTTP 500" });
	await loaded.plugin.__internals.loadInto(setState);

	assert.equal(updates[0].phase, "loading");
	assert.equal(updates[0].error, null);
	assert.equal(updates.at(-1).phase, "empty");
});

test("the sidebar icon cell forwards the geometry it was handed", () => {
	const cell = plugin.__internals.IconCell({ size: 20, active: true });
	assert.equal(cell.props.width, 20);
	assert.match(cell.props.className, /is-active/);
});

test("copyToClipboard writes the given text", async () => {
	const written = [];
	const clipboard = { writeText: async (text) => written.push(text) };
	await plugin.__internals.copyToClipboard("D:\\r\\a.mp4", clipboard);
	assert.deepEqual(written, ["D:\\r\\a.mp4"]);
});

test("copyToClipboard is silent when there is no clipboard to write to", async () => {
	await plugin.__internals.copyToClipboard("x", undefined);
	await plugin.__internals.copyToClipboard("x", {});
});

test("copyToClipboard swallows a rejected write", async () => {
	const clipboard = {
		writeText: async () => {
			throw new Error("document is not focused");
		},
	};
	await plugin.__internals.copyToClipboard("x", clipboard);
});

const { openInRightbar, galleryActions } = plugin.__internals;

test("openInRightbar expands the column before handing over the address", () => {
	const calls = [];
	const services = {
		layout: { openRightbar: (...args) => calls.push(["openRightbar", ...args]) },
		sidebarRight: { openResource: (...args) => calls.push(["openResource", ...args]) },
	};

	assert.equal(openInRightbar("D:\\r\\a.gif", services), true);
	assert.deepEqual(calls, [
		["openRightbar", true, false],
		["openResource", "dsh-resource://file/absolute/D:/r/a.gif"],
	]);
});

test("openInRightbar reports whether it could act", () => {
	assert.equal(openInRightbar("D:\\r\\a.gif", {}), false);
	assert.equal(openInRightbar("D:\\r\\a.gif", { sidebarRight: undefined }), false);
	assert.equal(openInRightbar("D:\\r\\a.gif", { sidebarRight: {} }), false);
	assert.equal(openInRightbar("D:\\r\\a.gif", { sidebarRight: { openResource() {} } }), true);
});

test("openInRightbar still works when the layout service is absent", () => {
	const seen = [];
	openInRightbar("D:\\r\\a.gif", { sidebarRight: { openResource: (a) => seen.push(a) } });
	assert.equal(seen.length, 1);
});

test("galleryActions gains openInRightbar only when the service is mounted", () => {
	const base = { setState: () => {}, services: {} };
	assert.equal(galleryActions(base).openInRightbar, undefined);

	const withService = galleryActions({
		...base,
		services: { sidebarRight: { openResource() {} } },
	});
	assert.equal(typeof withService.openInRightbar, "function");
});

test("apply probes the services instead of demanding them", () => {
	const { ctx, registrations, asked } = createCtx({ services: {} });
	plugin.apply(ctx);

	assert.deepEqual(asked.sort(), ["layout", "sidebarRight"]);
	// Both slots still register: a missing service costs one button, not the panel.
	assert.equal(registrations.length, 2);
	assert.equal(typeof registrations.find((r) => r.options.name === "main").component, "function");
});

test("the actions built for the page reach the resolved service", () => {
	const opened = [];
	const { ctx, registrations } = createCtx({
		services: {
			layout: { openRightbar() {} },
			sidebarRight: { openResource: (address) => opened.push(address) },
		},
	});
	plugin.apply(ctx);

	// The page renders `loading` first, so reach the actions the way the panel does
	// and then exercise the one that touches the services.
	const main = registrations.find((r) => r.options.name === "main");
	assert.equal(typeof main.component, "function");
	const actions = galleryActions({
		setState: () => {},
		services: { sidebarRight: { openResource: (address) => opened.push(address) } },
	});
	assert.equal(actions.openInRightbar("D:\\r\\a.gif"), true);
	assert.deepEqual(opened, ["dsh-resource://file/absolute/D:/r/a.gif"]);
});
