import assert from "node:assert/strict";
import { test } from "node:test";

import { loadClient, makeRun } from "./harness.mjs";

const { plugin } = loadClient();
const { galleryView, galleryIcon } = plugin.__internals;

function walk(node, out = []) {
	if (node === null || node === undefined || node === false) return out;
	if (Array.isArray(node)) {
		for (const child of node) walk(child, out);
		return out;
	}
	if (typeof node === "object" && "type" in node) {
		out.push(node);
		walk(node.props?.children, out);
		return out;
	}
	return out;
}

const textOf = (node) =>
	walk(node)
		.flatMap((el) => (Array.isArray(el.props?.children) ? el.props.children : []))
		.filter((child) => typeof child === "string")
		.join(" ");

const byClass = (node, className) =>
	walk(node).find((el) => String(el.props?.className ?? "").includes(className));

test("an empty library explains what to do next", () => {
	const tree = galleryView({ phase: "empty", runs: [], selected: null }, actions());
	assert.match(textOf(tree), /还没有动画/);
});

test("a load failure shows the reason and offers a retry", () => {
	const acts = actions();
	const tree = galleryView(
		{ phase: "error", runs: [], selected: null, error: "HTTP 404" },
		acts
	);
	assert.match(textOf(tree), /HTTP 404/);
	assert.ok(walk(tree).some((el) => el.props?.onClick === acts.refresh));
});

test("every run becomes a card with its preview, title and relative time", () => {
	const run = makeRun();
	const tree = galleryView({ phase: "ready", runs: [run], selected: null }, actions());
	const images = walk(tree).filter((el) => el.type === "img");
	assert.equal(images.length, 1);
	assert.ok(images[0].props.src.startsWith("/api/file?path="));
	assert.match(textOf(tree), /欧拉恒等式/);
});

test("a failed run is marked rather than hidden silently", () => {
	const run = makeRun({ status: "failed", title: "崩掉的一次" });
	const tree = galleryView(
		{ phase: "ready", runs: [run], selected: null, includeFailed: true },
		actions()
	);
	assert.match(textOf(tree), /失败/);
});

test("a run without a preview still renders a card", () => {
	const run = makeRun({ assets: { mp4: "D:\\r\\a.mp4" } });
	const tree = galleryView({ phase: "ready", runs: [run], selected: null }, actions());
	assert.equal(walk(tree).filter((el) => el.type === "img").length, 0);
	assert.match(textOf(tree), /欧拉恒等式/);
});

test("clicking a card selects that run", () => {
	const run = makeRun();
	const acts = actions();
	const tree = galleryView({ phase: "ready", runs: [run], selected: null }, acts);
	// Not "the first element with an onClick": the toolbar renders before the grid
	// and its refresh button would be found first.
	const card = byClass(tree, "manim-gallery__card");
	assert.ok(card, "no card was rendered");
	card.props.onClick();
	assert.deepEqual(acts.selected, ["20260912-153012-a1b2"]);
});

test("the detail view plays the MP4 with native controls", () => {
	const run = makeRun();
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, actions());
	const video = walk(tree).find((el) => el.type === "video");
	assert.ok(video, "the detail view must offer the MP4");
	assert.equal(video.props.controls, true);
	assert.ok(video.props.src.startsWith("/api/file?path="));
	assert.ok(video.props.src.includes(encodeURIComponent(".mp4")));
});

test("the detail view falls back to the poster when there is no MP4", () => {
	const run = makeRun({
		assets: {
			preview: "D:\\r\\a.gif",
			previewKind: "gif",
			poster: "D:\\r\\a.png",
		},
	});
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, actions());
	assert.equal(walk(tree).find((el) => el.type === "video"), undefined);
	assert.ok(walk(tree).some((el) => el.type === "img"));
});

test("the detail view shows the metadata a reader would ask for", () => {
	const run = makeRun();
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, actions());
	const body = textOf(tree);
	assert.match(body, /equation/);
	assert.match(body, /公式推导/);
	assert.match(body, /draft/);
	assert.match(body, /10\.4/);
});

test("the detail view offers a way back and a way to copy the path", () => {
	const run = makeRun();
	const acts = actions();
	const copied = [];
	acts.copyPath = (path) => copied.push(path);
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, acts);

	const buttons = walk(tree).filter((el) => typeof el.props?.onClick === "function");
	assert.ok(buttons.some((el) => el.props.onClick === acts.back), "no back button");

	const copy = byClass(tree, "manim-gallery__copy");
	assert.ok(copy, "no copy button");
	copy.props.onClick();
	assert.deepEqual(copied, [run.assets.mp4]);
});

test("a selection that is no longer in the list falls back to the grid", () => {
	const tree = galleryView(
		{ phase: "ready", runs: [makeRun()], selected: "gone" },
		actions()
	);
	assert.equal(walk(tree).find((el) => el.type === "video"), undefined);
	assert.match(textOf(tree), /欧拉恒等式/);
});

test("the toolbar exposes search, tool filter, sort and refresh", () => {
	const acts = actions();
	const tree = galleryView({ phase: "ready", runs: [makeRun()], selected: null }, acts);
	const controls = walk(tree);
	assert.ok(controls.some((el) => el.type === "input"));
	assert.ok(controls.some((el) => el.type === "select"));
	assert.ok(controls.some((el) => el.props?.onClick === acts.refresh));
});

test("the icon sizes itself from the sidebar and reflects the active state", () => {
	const idle = galleryIcon({ size: 18, active: false });
	const active = galleryIcon({ size: 16, active: true });
	assert.equal(idle.props.width, 18);
	assert.equal(active.props.width, 16);
	assert.notEqual(idle.props.className, active.props.className);
	assert.match(idle.props.className, /manim-gallery__glyph/);
});

test("the view never builds a write request", () => {
	// The panel is read-only by construction: a hand-written packaged plugin has no
	// client-to-host call path, so anything that mutates state belongs on the MCP.
	const run = makeRun();
	const tree = galleryView({ phase: "ready", runs: [run], selected: run.runId }, actions());
	for (const el of walk(tree)) {
		for (const value of Object.values(el.props ?? {})) {
			if (typeof value === "string") {
				assert.ok(!/method\s*:|POST|DELETE|PUT/i.test(value));
			}
		}
	}
});

function actions() {
	const acts = {
		selected: [],
		refresh: () => {},
		select: (runId) => acts.selected.push(runId),
		back: () => {},
		copyPath: () => {},
		setQuery: () => {},
		setTool: () => {},
		setSort: () => {},
		setIncludeFailed: () => {},
	};
	return acts;
}
