import assert from "node:assert/strict";
import { test } from "node:test";

import { loadClient } from "./harness.mjs";

const { plugin } = loadClient();
const { MediaView, fileUrl } = plugin.__internals;

function settled(media, extras = []) {
	return {
		kind: "tool-result",
		call: { name: "mcp__media__publish_file", argsRaw: "{}" },
		content: [
			{ type: "text", text: JSON.stringify({ ok: true, media, extras, warnings: [] }) },
		],
		isError: false,
	};
}

const VIDEO = {
	kind: "video",
	mime: "video/mp4",
	name: "clip.mp4",
	reference: "/myprogram/dshplugin/out/clip.mp4",
	bytes: 1234,
};

test("fileUrl encodes the reference into the same-origin endpoint", () => {
	assert.equal(
		fileUrl("/myprogram/dshplugin/out/clip.mp4"),
		"/api/file?path=%2Fmyprogram%2Fdshplugin%2Fout%2Fclip.mp4",
	);
});

test("a video renders a <video> with controls and no autoplay", () => {
	const tree = MediaView(settled(VIDEO));
	const video = find(tree, "video");
	assert.ok(video, "no <video> in the tree");
	assert.equal(video.props.controls, true);
	assert.notEqual(video.props.autoPlay, true);
	assert.match(String(video.props.src), /^\/api\/file\?path=/);
});

test("audio renders <audio> and images render <img>", () => {
	assert.ok(find(MediaView(settled({ ...VIDEO, kind: "audio", mime: "audio/wav" })), "audio"));
	assert.ok(find(MediaView(settled({ ...VIDEO, kind: "image", mime: "image/png" })), "img"));
});

test("a PDF renders its rasterised pages as images plus a way to read the whole file", () => {
	const pdf = { ...VIDEO, kind: "pdf", mime: "application/pdf", name: "r.pdf", pages: 12 };
	const extras = [{ kind: "image", mime: "image/png", name: "page-1.png", reference: "/p/1.png" }];
	const tree = MediaView(settled(pdf, extras));
	assert.ok(find(tree, "img"), "the page preview must be inline");
	assert.ok(findByClass(tree, "manim-media__open"), "the full-document button is missing");
});

test("an unrenderable kind still shows name, size and an open action", () => {
	const tree = MediaView(settled({ ...VIDEO, kind: "other", name: "a.zip", bytes: 2048 }));
	assert.match(textOf(tree), /a\.zip/);
	assert.ok(findByClass(tree, "manim-media__open"));
});

test("a running call shows a loading state, never an empty player", () => {
	const tree = MediaView({ callId: "x", name: "mcp__media__publish_file", argsRaw: "{}" });
	assert.equal(find(tree, "video"), null);
	assert.ok(findByClass(tree, "manim-media__pending"));
});

test("a refusal shows the reason and the hint", () => {
	const block = {
		kind: "tool-result",
		content: [
			{
				type: "text",
				text: JSON.stringify({ ok: false, reason: "too-large", detail: "33 > 32", hint: "压缩" }),
			},
		],
		isError: false,
	};
	const tree = MediaView(block);
	assert.match(textOf(tree), /too-large/);
	assert.match(textOf(tree), /压缩/);
});

test("a malformed result degrades to a plain row instead of throwing", () => {
	const tree = MediaView({ kind: "tool-result", content: [{ type: "text", text: "{{{" }], isError: false });
	assert.ok(tree, "must render something");
	assert.equal(find(tree, "video"), null);
});

// --- tiny tree helpers -------------------------------------------------------

function find(node, type) {
	if (node === null || typeof node !== "object") return null;
	if (Array.isArray(node)) {
		for (const child of node) {
			const hit = find(child, type);
			if (hit) return hit;
		}
		return null;
	}
	if (node.type === type) return node;
	return find(node.props?.children, type);
}

function findByClass(node, className) {
	if (node === null || typeof node !== "object") return null;
	if (Array.isArray(node)) {
		for (const child of node) {
			const hit = findByClass(child, className);
			if (hit) return hit;
		}
		return null;
	}
	const classes = String(node.props?.className ?? "");
	if (classes.split(/\s+/).includes(className)) return node;
	return findByClass(node.props?.children, className);
}

function textOf(node, out = []) {
	if (node === null || node === undefined) return out.join("");
	if (typeof node === "string" || typeof node === "number") {
		out.push(String(node));
		return out.join("");
	}
	if (Array.isArray(node)) {
		for (const child of node) textOf(child, out);
		return out.join("");
	}
	textOf(node.props?.children, out);
	return out.join("");
}
