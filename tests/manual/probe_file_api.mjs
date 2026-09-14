/**
 * Prove the in-answer Markdown reference actually loads over /api/file.
 *
 * The engine emits a `/`-rooted reference and the Host resolves it with
 * `node:path.resolve` against the `fs-sandbox` cwd. This script does not simulate
 * that any more — it signs a real browser-session cookie with the secret the local
 * Host already stores and asks the running server for the bytes, so a 200 here means
 * the animation really renders in the answer.
 *
 *   node tests/manual/probe_file_api.mjs            # newest run in renders/index.json
 *   node tests/manual/probe_file_api.mjs <abs-path> # a specific artifact
 *
 * Env: DSH_SECRET (required) — record secret from ~/.dsh/.credentials.yaml.
 */

import { createHash, createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const ORIGIN = process.env.DSH_ORIGIN ?? "http://127.0.0.1:3080";
const AUTHORITY = new URL(ORIGIN).host;
const RENDER_ROOT = resolve(process.env.DSH_RENDER_ROOT ?? "D:/myprogram/dshplugin/renders");

function sessionCookie() {
  const raw = process.env.DSH_SECRET;
  if (!raw) throw new Error("DSH_SECRET is required");
  const secret = Buffer.from(raw, "base64url");
  if (secret.byteLength !== 32) {
    throw new Error(`secret must decode to 32 bytes, got ${String(secret.byteLength)}`);
  }
  const name =
    "dsh-auth-" + createHash("sha256").update(AUTHORITY).digest().toString("base64url");
  const now = Date.now();
  const payload = {
    version: 1,
    authority: AUTHORITY,
    issuedAt: now,
    expiresAt: now + 86_400_000,
  };
  const body = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const signature = createHmac("sha256", secret).update(body).digest().toString("base64url");
  return `${name}=v1.${body}.${signature}`;
}

/** The reference the engine emits: absolute path, drive letter removed. */
function rootedReference(absolute) {
  const posix = absolute.replaceAll("\\", "/");
  const match = /^([A-Za-z]):(\/.*)$/.exec(posix);
  if (!match) throw new Error(`no drive in ${absolute}`);
  return match[2];
}

function newestArtifact() {
  const index = JSON.parse(readFileSync(resolve(RENDER_ROOT, "index.json"), "utf8"));
  const runs = Array.isArray(index) ? index : index.runs;
  for (const run of runs) {
    const preview = run?.assets?.preview;
    if (preview) return resolve(preview);
  }
  throw new Error("no run in index.json carries a preview");
}

async function probe(sendCookie, reference, label) {
  const url = `${ORIGIN}/api/file?path=${encodeURIComponent(reference)}`;
  const headers = sendCookie ? { cookie: sessionCookie() } : {};
  let response;
  try {
    response = await fetch(url, { method: "HEAD", headers });
  } catch (error) {
    console.log(`ERROR   ${label.padEnd(46)} ${String(error.message)}`);
    return;
  }
  const type = response.headers.get("content-type") ?? "-";
  const length = response.headers.get("content-length") ?? "-";
  console.log(
    `${String(response.status).padEnd(7)} ${label.padEnd(46)} ${type} ${length}B`,
  );
  // The security headers decide what can be done with the bytes: a `sandbox` CSP is
  // what puts "render this in an <iframe>" in question, and `nosniff` is why a wrong
  // content-type cannot be recovered from. Printing them here is what turns "the
  // viewer will not open it" into a readable cause.
  for (const name of [
    "content-security-policy",
    "content-disposition",
    "cache-control",
    "x-content-type-options",
  ]) {
    const value = response.headers.get(name);
    if (value) console.log(`        ${name}: ${value}`);
  }
}

const artifact = process.argv[2] ? resolve(process.argv[2]) : newestArtifact();
const reference = rootedReference(artifact);
const basename = artifact.split(/[\\/]/).pop();

console.log(`origin      = ${ORIGIN}`);
console.log(`authority   = ${AUTHORITY}`);
console.log(`artifact    = ${artifact}`);
console.log(`reference   = ${reference}`);
console.log("");

await probe(true, reference, `emitted form  ${reference}`);
await probe(true, `/${basename}`, "old form (render root's name only)");
await probe(true, `/${artifact.replaceAll("\\", "/")}`, "drive-prefixed form /D:/...");
await probe(true, rootedReference(resolve(RENDER_ROOT, "index.json")), "index.json");
await probe(true, rootedReference(resolve(RENDER_ROOT, "does-not-exist.gif")), "absent file");
await probe(false, reference, "emitted form, no cookie (expect 401)");
