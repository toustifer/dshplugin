export const name = "dsh-media-view";
export const client = "./client.js";

// This package is primarily a client plugin, but its bundle is also inserted
// into the Host Cordis tree. Keep a no-op Host entry so Cordis accepts it.
export function apply() {}
