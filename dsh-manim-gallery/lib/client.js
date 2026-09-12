window.__ModuleLoader__.load({
	id: "dsh-manim-gallery",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });

		const react = require("react");
		const h = react.createElement;

		/** The panel id. The sidebar entry and the `main` key must be this one string. */
		const PANEL_ID = "manim-gallery";

		function GalleryIcon(props) {
			return h("span", { className: "manim-gallery__glyph", "aria-hidden": "true" }, "▦");
		}

		function GalleryPage() {
			return h("div", { className: "manim-gallery" }, "动画库");
		}

		function apply(ctx) {
			ctx.slots.inject("sidebar.panellist", () =>
				ctx.slots.register(
					{ name: "sidebar.panellist", id: PANEL_ID, order: 40, label: "动画库" },
					GalleryIcon
				)
			);
			ctx.slots.inject("main", () =>
				ctx.slots.register({ name: "main", key: PANEL_ID }, GalleryPage)
			);
		}

		exports.apply = apply;
		exports.inject = ["slots"];
		return module.exports;
	},
});
