// Mirrors the gallery harness: evaluate the browser bundle against mock surfaces so the
// renderer can be tested without a browser or a running DSH.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const CLIENT_PATH = resolve(HERE, "..", "lib", "client.js");

export function createReactStub() {
	const hooks = { states: [], setters: [], effects: [], refs: [] };
	return {
		hooks,
		Fragment: Symbol.for("react.fragment"),
		createElement(type, props, ...children) {
			return { type, props: { ...(props ?? {}), children: children.flat(Infinity) } };
		},
		useState(initial) {
			const value = typeof initial === "function" ? initial() : initial;
			hooks.states.push(value);
			hooks.setters.push(() => {});
			return [value, () => {}];
		},
		useEffect(fn) {
			hooks.effects.push({ fn });
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

export function createCtx({ services = {} } = {}) {
	const registrations = [];
	const asked = [];
	const ctx = {
		slots: {
			inject(_key, callback) {
				return callback();
			},
			register(options, component) {
				registrations.push({ options, component });
				return () => {};
			},
		},
		get(name) {
			asked.push(name);
			return services[name] ?? ctx[name];
		},
		on() {
			return () => {};
		},
	};
	for (const [name, value] of Object.entries(services)) ctx[name] = value;
	return { registrations, asked, ctx };
}

export function loadClient() {
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
	const react = createReactStub();
	const loader = (specifier) => {
		if (specifier === "react") return react;
		throw new Error(`unexpected require(${JSON.stringify(specifier)})`);
	};
	new Function("require", readFileSync(CLIENT_PATH, "utf8"))(loader);
	if (captured === null) throw new Error("client.js did not call __ModuleLoader__.load");
	return { entry: captured, plugin: captured.factory(loader), react };
}
