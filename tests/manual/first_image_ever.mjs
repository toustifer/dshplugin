/**
 * One-off archaeology: when did THIS machine's DSH first carry an image in a message,
 * and which side of the conversation was it on?
 *
 * Two traps this had to get past, both found by measuring rather than reasoning:
 *   1. The filename carries the format version (`session.v3.jsonl.zstd`), and it has
 *      changed across migrations — matching one literal name silently skips files.
 *   2. The log is a sequence of CONCATENATED zstd frames, one per append (2769 of them
 *      in the current session). `zstdDecompressSync` and `createZstdDecompress()` both
 *      stop after the first frame, so they read 204 bytes out of 4.4 MB and report
 *      "1 record". Splitting on the frame magic and decompressing each frame is what
 *      actually reads the file.
 *
 * Run: node tests/manual/first_image_ever.mjs
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { zstdDecompressSync } from "node:zlib";

const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd]);
const ROOT = join(process.env.USERPROFILE, ".dsh", "sessions");

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/^session(\.v\d+)?\.jsonl\.zstd$/.test(entry.name)) out.push(full);
  }
  return out;
}

/** Every frame in the file, concatenated. */
function readLog(path) {
  const buffer = readFileSync(path);
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
      // A false magic inside compressed bytes splits a frame in two; the halves fail
      // to decode and are dropped rather than corrupting the scan.
    }
  }
  return Buffer.concat(parts).toString("utf8");
}

const files = walk(ROOT)
  .map((path) => ({ path, mtime: statSync(path).mtimeMs }))
  .sort((a, b) => a.mtime - b.mtime);

console.log(`session files: ${String(files.length)}\n`);

let found = 0;
for (const file of files) {
  let text;
  try {
    text = readLog(file.path);
  } catch {
    continue;
  }
  if (!text.includes('"image"')) continue;

  for (const line of text.split("\n")) {
    if (!line.includes('"image"')) continue;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      continue;
    }
    const json = JSON.stringify(record);
    if (!/image/.test(json)) continue;
    // Skip records that merely mention the word (a tool name, a prompt) and keep the
    // ones that actually carry an attachment.
    if (!/attachment|imageId|"type":"image"/.test(json)) continue;

    const at = record.timestamp ?? record.time ?? record.createdAt ?? record.at ?? "?";
    console.log(`at      = ${String(at)}`);
    console.log(`session = ${file.path.replace(ROOT, "")}`);
    console.log(`mtime   = ${new Date(file.mtime).toISOString()}`);
    console.log(`record  = ${json.slice(0, 600)}`);
    console.log("");
    found += 1;
    break; // earliest per file is enough
  }
  if (found >= 6) break;
}

if (found === 0) console.log("no record carrying an image attachment was found");
