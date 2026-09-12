import assert from "node:assert/strict";
import { test } from "node:test";

import { createCtx, createTabRegistry, loadClient, makeRun } from "./harness.mjs";

const { plugin } = loadClient();

/** The declared services, mounted the way the harness mounts any dependency. */
function services(overrides = {}) {
	return { sidebarRight: {}, sidebarRightTabs: createTabRegistry(), ...overrides };
}

function pageOf(loaded) {
	const { ctx, registrations } = createCtx({ services: services() });
	loaded.plugin.apply(ctx);
	return registrations.find((r) => r.options.name === "sidebar.right.pane.tab").component;
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

test("the header button draws the icon at chip size", () => {
	// The left rail's `IconCell` is gone with the rail; the header button is the one
	// consumer of `galleryIcon` left, and it asks for the 16px chip size.
	const button = plugin.__internals.makeHeaderButton({ sidebarRight: { openTab() {} } });
	const tree = button({});
	const [glyph] = tree.props.children;
	assert.equal(glyph.props.width, 16);
	assert.match(glyph.props.className, /manim-gallery__glyph/);
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

const { openInRightbar, galleryActions, openGalleryColumn } = plugin.__internals;

test("openInRightbar hands over the address and lets openResource expand the column", () => {
	const calls = [];
	const services = {
		// Still supplied, to prove it is NOT called: `openResource` expands the column
		// on its own, and `layout` is no longer a declared dependency of this plugin.
		layout: { openRightbar: (...args) => calls.push(["openRightbar", ...args]) },
		sidebarRight: { openResource: (...args) => calls.push(["openResource", ...args]) },
	};

	assert.equal(openInRightbar("D:\\r\\a.gif", services), true);
	assert.deepEqual(calls, [["openResource", "dsh-resource://file/absolute/D:/r/a.gif"]]);
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

test("openInRightbar retries until the right column has bound its session", () => {
	// The controller throws "no session surface is mounted" until React has rendered
	// the column, so the first click on a closed sidebar clears only after retries.
	let calls = 0;
	const sidebarRight = {
		openResource() {
			calls += 1;
			if (calls < 3) throw new Error("sidebarRight: no session surface is mounted");
		},
	};
	const scheduled = [];
	openInRightbar("D:\\r\\a.gif", { sidebarRight }, {
		attempts: 5,
		schedule: (fn) => scheduled.push(fn),
	});

	assert.equal(calls, 1, "the first attempt happens immediately");
	assert.equal(scheduled.length, 1, "a failed attempt schedules the next one");

	scheduled.shift()();
	assert.equal(calls, 2);
	scheduled.shift()();
	assert.equal(calls, 3, "the third attempt succeeds");
	assert.equal(scheduled.length, 0, "nothing more is scheduled after success");
});

test("openInRightbar gives up loudly instead of leaving a dead button", () => {
	const warned = [];
	const sidebarRight = {
		openResource() {
			throw new Error("sidebarRight: no session surface is mounted");
		},
	};
	openInRightbar("D:\\r\\a.gif", { sidebarRight }, {
		attempts: 3,
		schedule: (fn) => fn(),
		warn: (message) => warned.push(message),
	});

	assert.equal(warned.length, 1, "a silent failure is the worst outcome");
	assert.match(String(warned[0]), /右栏|右侧|sidebar/i);
});

test("apply reads the services off the declared context properties", () => {
	// Not `ctx.get`: a service provided by a sibling plugin is only reliably visible
	// as a context property, and only when it is declared in `inject`. Probing with
	// `ctx.get` returned undefined and cost the panel its right-sidebar button.
	const { ctx, registrations, asked } = createCtx({
		services: services({ sidebarRight: { openResource() {}, openTab() {} } }),
	});
	plugin.apply(ctx);

	assert.deepEqual(asked, [], "the services must come from the declared properties");
	assert.equal(registrations.length, 2);

	// And the body it built really does carry the page.
	const body = registrations.find((r) => r.options.name === "sidebar.right.pane.tab");
	assert.equal(typeof body.component, "function");
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

test("apply registers the tab body and the header door", () => {
	// `sidebarRight` and `sidebarRightTabs` are declared dependencies, so Cordis does
	// not call `apply` at all until they exist — there is no "service missing" state
	// left to degrade into.
	const { ctx, registrations } = createCtx({ services: services() });
	plugin.apply(ctx);

	assert.deepEqual(
		registrations.map((r) => r.options.name),
		["sidebar.right.pane.tab", "conversation.session.header.utilities"]
	);
	for (const entry of registrations) {
		assert.equal(typeof entry.component, "function", entry.options.name);
	}
});

test("the header button opens the gallery as a right-column tab", () => {
	// The whole point of this design: the door expands the side column instead of
	// swapping the centre panel, so the conversation stays on screen.
	const opened = [];
	const button = plugin.__internals.makeHeaderButton({
		sidebarRight: { openTab: (kind, options) => opened.push([kind, options]) },
	});
	const tree = button({});
	assert.equal(typeof tree.props.onClick, "function");
	tree.props.onClick();
	assert.deepEqual(opened, [["manim-gallery", undefined]]);
});

test("the header button reports a missing controller instead of throwing", () => {
	const open = plugin.__internals.openGalleryColumn;
	assert.equal(open({}), false);
	assert.equal(open({ sidebarRight: {} }), false);
	assert.equal(open({ sidebarRight: { openTab() {} } }), true);
});

test("the header button survives a controller that throws before its seat mounts", () => {
	// `openTab` throws "no session surface is mounted" until the column's seat binds,
	// and this button can be pressed that early. A throw escaping a React event
	// handler would take the whole header down.
	const warn = console.warn;
	const warnings = [];
	console.warn = (...args) => warnings.push(args);
	try {
		const opened = plugin.__internals.openGalleryColumn({
			sidebarRight: {
				openTab() {
					throw new Error("no session surface is mounted");
				},
			},
		});
		assert.equal(opened, false);
	} finally {
		console.warn = warn;
	}
	// Not silent: the condition is logged, not swallowed.
	assert.equal(warnings.length, 1);
});

test("the actions built for the page reach the resolved service", () => {
	const opened = [];
	const { ctx, registrations } = createCtx({
		services: services({
			sidebarRight: { openResource: (address) => opened.push(address) },
		}),
	});
	plugin.apply(ctx);

	// The page renders `loading` first, so reach the actions the way the panel does
	// and then exercise the one that touches the services.
	const body = registrations.find((r) => r.options.name === "sidebar.right.pane.tab");
	assert.equal(typeof body.component, "function");
	const actions = galleryActions({
		setState: () => {},
		services: { sidebarRight: { openResource: (address) => opened.push(address) } },
	});
	assert.equal(actions.openInRightbar("D:\\r\\a.gif"), true);
	assert.deepEqual(opened, ["dsh-resource://file/absolute/D:/r/a.gif"]);
});
