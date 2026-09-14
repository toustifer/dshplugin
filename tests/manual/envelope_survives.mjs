// Does our MCP envelope survive into the recorded tool result byte-for-byte?
//
// The naive search ("a record mentioning previewMarkdown") is useless here: this very
// session's own command output is logged too, and the search script's source contains
// the word. The predicate has to be "a text block that PARSES as our envelope".
import { readFileSync } from "node:fs";
import { zstdDecompressSync } from "node:zlib";

const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd]);
const buffer = readFileSync(process.argv[2]);

const starts = [];
for (let at = buffer.indexOf(MAGIC); at !== -1; at = buffer.indexOf(MAGIC, at + 4)) {
  starts.push(at);
}
const parts = [];
for (const [index, start] of starts.entries()) {
  const end = index + 1 < starts.length ? starts[index + 1] : buffer.length;
  try {
    parts.push(zstdDecompressSync(buffer.subarray(start, end)));
  } catch {
    /* a false magic splits a frame; the halves fail to decode and are dropped */
  }
}
const lines = Buffer.concat(parts).toString("utf8").split("\n").filter(Boolean);

function textBlocks(node, out = []) {
  if (node === null || typeof node !== "object") return out;
  if (Array.isArray(node)) {
    for (const item of node) textBlocks(item, out);
    return out;
  }
  if (node.type === "text" && typeof node.text === "string") out.push(node.text);
  for (const value of Object.values(node)) textBlocks(value, out);
  return out;
}

let found = null;
let examined = 0;
for (const line of lines) {
  if (!line.includes("tool/result")) continue;
  let record;
  try {
    record = JSON.parse(line);
  } catch {
    continue;
  }
  if (record?.type !== "tool/result") continue;
  examined += 1;
  for (const text of textBlocks(record)) {
    const trimmed = text.trim();
    if (!trimmed.startsWith("{")) continue;
    let parsed;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      continue;
    }
    if (parsed?.ok === true && typeof parsed.runId === "string") {
      found = { record, text, parsed };
      break;
    }
  }
  if (found) break;
}

console.log(`tool/result records examined: ${String(examined)}`);
if (!found) {
  console.log("no tool result carried a parseable envelope");
  process.exit(0);
}
console.log(`\nenvelope parsed OK. keys = ${Object.keys(found.parsed).join(",")}`);
console.log(`previewMarkdown = ${String(found.parsed.previewMarkdown)}`);
console.log(`\ntool call name = ${JSON.stringify(found.record.data?.message?.source?.callId ?? null)}`);
console.log(`\n--- recorded text block, verbatim (first 220 chars) ---`);
console.log(found.text.slice(0, 220));
console.log(`\n--- byte-identical to a fresh dumps()? ---`);
const redumped = JSON.stringify(found.parsed, null, 2);
console.log(`re-dump matches recorded text: ${String(redumped === found.text)}`);
