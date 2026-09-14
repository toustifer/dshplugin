// Parsing is the defensive layer: a malformed envelope must degrade to a plain row,
// never throw, because a throw inside a tool view takes the whole conversation down.
import assert from "node:assert/strict";
import { test } from "node:test";

import { loadClient } from "./harness.mjs";

const { plugin } = loadClient();
const { readEnvelope, readMedia } = plugin.__internals;

function resultWith(blocks) {
	return { kind: "tool-result", content: blocks, isError: false };
}

test("reads the envelope out of the single text block", () => {
	const payload = { ok: true, media: { kind: "video", name: "a.mp4" } };
	const found = readEnvelope(resultWith([{ type: "text", text: JSON.stringify(payload, null, 2) }]));
	assert.deepEqual(found, payload);
});

test("ignores non-text blocks around it", () => {
	const payload = { ok: true, media: { kind: "image", name: "a.png" } };
	const found = readEnvelope(
		resultWith([
			{ type: "text", text: "noise" },
			{ type: "image", attachment: {} },
			{ type: "text", text: JSON.stringify(payload) },
		]),
	);
	assert.deepEqual(found, payload);
});

test("a malformed envelope yields null instead of throwing", () => {
	assert.equal(readEnvelope(resultWith([{ type: "text", text: "{ not json" }])), null);
	assert.equal(readEnvelope(resultWith([{ type: "text", text: "[1,2,3]" }])), null);
	assert.equal(readEnvelope(resultWith([])), null);
	assert.equal(readEnvelope(undefined), null);
});

test("readMedia returns null for every shape that is not a usable descriptor", () => {
	assert.equal(readMedia(null), null);
	assert.equal(readMedia({ ok: false, reason: "missing" }), null);
	assert.equal(readMedia({ ok: true }), null);
	assert.equal(readMedia({ ok: true, media: { kind: "video" } }), null); // no reference
	assert.equal(readMedia({ ok: true, media: { reference: "/a" } }), null); // no kind
	assert.deepEqual(readMedia({ ok: true, media: { kind: "video", reference: "/a" } }), {
		kind: "video",
		reference: "/a",
	});
});
