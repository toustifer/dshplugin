import assert from "node:assert/strict";
import { test } from "node:test";

import { makeRun } from "./harness.mjs";
import { loadClient } from "./harness.mjs";

const { plugin } = loadClient();
const {
	RENDER_ROOT,
	INDEX_PATH,
	fileUrl,
	indexUrl,
	relativeTime,
	sortRuns,
	filterRuns,
	loadIndex,
	runTool,
} = plugin.__internals;

test("the render root is a slash path the Host can serve", () => {
	assert.match(RENDER_ROOT, /^[A-Za-z]:\//);
	assert.equal(INDEX_PATH, `${RENDER_ROOT}/index.json`);
});

test("fileUrl routes an absolute path through the authenticated file endpoint", () => {
	const url = fileUrl("D:\\myprogram\\dshplugin\\renders\\a\\out\\S.gif");
	assert.equal(
		url,
		"/api/file?path=" + encodeURIComponent("/D:/myprogram/dshplugin/renders/a/out/S.gif")
	);
});

test("fileUrl accepts a path that is already in slash form", () => {
	assert.equal(fileUrl("/D:/r/a.gif"), "/api/file?path=" + encodeURIComponent("/D:/r/a.gif"));
});

test("fileUrl does not double the leading slash", () => {
	assert.ok(!fileUrl("/D:/a.gif").includes(encodeURIComponent("//D:")));
});

test("fileUrl escapes characters that would break the query string", () => {
	const url = fileUrl("D:\\my program\\a&b.gif");
	assert.ok(!url.includes(" "));
	assert.ok(!url.includes("&b"));
});

test("indexUrl points at the render root's index", () => {
	assert.equal(indexUrl(), fileUrl(INDEX_PATH));
});

test("relativeTime speaks in the units a reader scans for", () => {
	const now = Date.parse("2026-09-12T20:00:00+08:00");
	assert.equal(relativeTime("2026-09-12T19:59:30+08:00", now), "刚刚");
	assert.equal(relativeTime("2026-09-12T19:52:00+08:00", now), "8 分钟前");
	assert.equal(relativeTime("2026-09-12T18:00:00+08:00", now), "2 小时前");
	assert.equal(relativeTime("2026-09-11T20:00:00+08:00", now), "昨天");
	assert.equal(relativeTime("2026-09-05T20:00:00+08:00", now), "7 天前");
	assert.equal(relativeTime("2026-06-01T20:00:00+08:00", now), "2026-06-01");
});

test("relativeTime tolerates a missing or unparsable timestamp", () => {
	assert.equal(relativeTime(null, Date.now()), "");
	assert.equal(relativeTime("not a date", Date.now()), "");
});

test("sortRuns defaults to newest first", () => {
	const runs = [
		makeRun({ runId: "a", createdAt: "2026-09-12T10:00:00+08:00" }),
		makeRun({ runId: "b", createdAt: "2026-09-12T12:00:00+08:00" }),
		makeRun({ runId: "c", createdAt: "2026-09-12T11:00:00+08:00" }),
	];
	assert.deepEqual(sortRuns(runs, "newest").map(runTool), ["b", "c", "a"]);
});

test("sortRuns can order by duration", () => {
	const runs = [
		makeRun({ runId: "a", durationSec: 5 }),
		makeRun({ runId: "b", durationSec: 20 }),
		makeRun({ runId: "c", durationSec: 12 }),
	];
	assert.deepEqual(sortRuns(runs, "longest").map(runTool), ["b", "c", "a"]);
});

test("sortRuns does not mutate its input", () => {
	const runs = [
		makeRun({ runId: "a", createdAt: "2026-09-12T10:00:00+08:00" }),
		makeRun({ runId: "b", createdAt: "2026-09-12T12:00:00+08:00" }),
	];
	sortRuns(runs, "newest");
	assert.deepEqual(runs.map(runTool), ["a", "b"]);
});

test("filterRuns hides failed runs by default", () => {
	const runs = [makeRun({ runId: "a" }), makeRun({ runId: "b", status: "failed" })];
	assert.deepEqual(filterRuns(runs, {}).map(runTool), ["a"]);
});

test("filterRuns can show failed runs on request", () => {
	const runs = [makeRun({ runId: "a" }), makeRun({ runId: "b", status: "failed" })];
	assert.deepEqual(filterRuns(runs, { includeFailed: true }).map(runTool), ["a", "b"]);
});

test("filterRuns narrows by tool", () => {
	const runs = [makeRun({ runId: "a", tool: "equation" }), makeRun({ runId: "b", tool: "graph" })];
	assert.deepEqual(filterRuns(runs, { tool: "graph" }).map(runTool), ["b"]);
});

test("filterRuns searches title and tool, case-insensitively", () => {
	const runs = [
		makeRun({ runId: "a", title: "欧拉恒等式", tool: "equation" }),
		makeRun({ runId: "b", title: "sin 与切线", tool: "graph" }),
	];
	assert.deepEqual(filterRuns(runs, { query: "切线" }).map(runTool), ["b"]);
	assert.deepEqual(filterRuns(runs, { query: "GRAPH" }).map(runTool), ["b"]);
	assert.deepEqual(filterRuns(runs, { query: "不存在" }).map(runTool), []);
});

test("filterRuns treats a blank query as no filter", () => {
	const runs = [makeRun({ runId: "a" })];
	assert.equal(filterRuns(runs, { query: "   " }).length, 1);
});

test("filterRuns survives entries with missing fields", () => {
	const runs = [{ runId: "x" }, makeRun({ runId: "a" })];
	assert.deepEqual(filterRuns(runs, {}).map(runTool), ["x", "a"]);
});

test("loadIndex asks for the index through fileUrl", async () => {
	const seen = [];
	const result = await loadIndex(async (url) => {
		seen.push(url);
		return { ok: true, status: 200, json: async () => ({ updatedAt: "t", runs: [makeRun()] }) };
	});
	assert.deepEqual(seen, [indexUrl()]);
	assert.equal(result.runs.length, 1);
	assert.equal(result.updatedAt, "t");
});

test("loadIndex reports a non-OK response with its status", async () => {
	await assert.rejects(
		() => loadIndex(async () => ({ ok: false, status: 404, json: async () => ({}) })),
		/404/
	);
});

test("loadIndex rejects a body that is not an object with runs", async () => {
	await assert.rejects(
		() => loadIndex(async () => ({ ok: true, status: 200, json: async () => [1, 2] })),
		/runs/
	);
});

test("loadIndex tolerates a missing updatedAt", async () => {
	const result = await loadIndex(async () => ({ ok: true, status: 200, json: async () => ({ runs: [] }) }));
	assert.equal(result.updatedAt, null);
});
