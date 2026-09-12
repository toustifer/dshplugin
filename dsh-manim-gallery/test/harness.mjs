// Offline harness: evaluates the browser half of the plugin against mock Cordis
// surfaces, so the panel can be tested without a browser or a running DSH.
//
// `lib/client.js` is a plain script that calls `window.__ModuleLoader__.load`,
// exactly as the shipped client-bundle format does; `new Function` is how the
// harness plays that script's role.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const PACKAGE_ROOT = resolve(HERE, "..");
export const CLIENT_PATH = resolve(PACKAGE_ROOT, "lib", "client.js");

export function createReactStub() {
	// `hooks.updates` is what makes an effect's *outcome* assertable: the stub has
	// no re-render loop, so a test reads the state object the setter was handed
	// rather than the tree a real React would have painted. The setter applies a
	// functional update to the captured initial value, which is exact for the
	// single-update sequences these tests exercise and wrong for a chain — do not
	// use it to test reducer-like behaviour.
	const hooks = { states: [], setters: [], updates: [], effects: [], refs: [] };
	return {
		hooks,
		Fragment: Symbol.for("react.fragment"),
		createElement(type, props, ...children) {
			return { type, props: { ...(props ?? {}), children: children.flat(Infinity) } };
		},
		useState(initial) {
			const value = typeof initial === "function" ? initial() : initial;
			hooks.states.push(value);
			const setter = (next) => {
				const resolved = typeof next === "function" ? next(value) : next;
				hooks.updates.push(resolved);
				return resolved;
			};
			hooks.setters.push(setter);
			return [value, setter];
		},
		useEffect(fn, deps) {
			hooks.effects.push({ fn, deps });
		},
		useMemo(fn) {
			return fn();
		},
		useCallback(fn) {
			return fn;
		},
		useRef(value) {
			const ref = { current: value };
			hooks.refs.push(ref);
			return ref;
		},
	};
}

export function createCtx() {
	const registrations = [];
	return {
		registrations,
		/** The registration for one slot, matched by list `id` or keyed `key`. */
		find(name) {
			return registrations.find((entry) => entry.options.name === name);
		},
		ctx: {
			slots: {
				inject(key, callback) {
					return callback();
				},
				register(options, component) {
					registrations.push({ options, component });
					return () => {};
				},
			},
			get() {
				return undefined;
			},
			on() {
				return () => {};
			},
		},
	};
}

/** Evaluate lib/client.js and return the captured module entry plus its exports. */
export function loadClient({ fetchImpl } = {}) {
	let captured = null;
	globalThis.window = {
		__ModuleLoader__: {
			load(entry) {
				captured = entry;
			},
		},
		location: { protocol: "http:", origin: "http://127.0.0.1:3080" },
		addEventListener() {},
		removeEventListener() {},
	};
	globalThis.fetch =
		fetchImpl ??
		(async () => ({
			ok: true,
			status: 200,
			json: async () => ({ version: 1, updatedAt: null, runs: [] }),
		}));

	const react = createReactStub();
	const loader = (specifier) => {
		if (specifier === "react") return react;
		throw new Error(`unexpected require(${JSON.stringify(specifier)})`);
	};

	new Function("require", readFileSync(CLIENT_PATH, "utf8"))(loader);
	if (captured === null) throw new Error("client.js did not call __ModuleLoader__.load");
	return { entry: captured, plugin: captured.factory(loader), react };
}

/** A run entry shaped like the one manim-mcp writes into renders/index.json. */
export function makeRun(overrides = {}) {
	return {
		runId: "20260912-153012-a1b2",
		tool: "equation",
		sceneName: "EquationScene",
		title: "欧拉恒等式",
		status: "ok",
		quality: "draft",
		createdAt: "2026-09-12T15:30:12+08:00",
		durationSec: 10.4,
		renderSeconds: 9.8,
		assets: {
			mp4: "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\EquationScene.mp4",
			preview: "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\EquationScene.gif",
			previewKind: "gif",
			poster: "D:\\myprogram\\dshplugin\\renders\\20260912-153012-a1b2\\out\\EquationScene.png",
		},
		previewUrlPath: "/D:/myprogram/dshplugin/renders/20260912-153012-a1b2/out/EquationScene.gif",
		args: { steps: 3 },
		warnings: [],
		...overrides,
	};
}
