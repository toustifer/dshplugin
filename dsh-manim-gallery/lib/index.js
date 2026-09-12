/**
 * Host half.
 *
 * This plugin has nothing to do on the Host: the panel reads `renders/index.json`
 * through the already-authenticated `/api/file` channel, so it needs no Host
 * service, no RPC, and no filesystem access of its own. The entry exists because
 * the Cordis bundle expects a Host-side module, and it is the place a future
 * Host-side feature would go.
 */
export function apply(ctx) {
	// Intentionally empty.
}
