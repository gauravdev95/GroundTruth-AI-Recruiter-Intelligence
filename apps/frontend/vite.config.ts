import { defineConfig } from "vite";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * Injects `<link rel="preload">` for the two font faces the hero is set in.
 *
 * Fonts referenced only by `@font-face` are not requested until the browser lays
 * out text that needs them — after the stylesheet has downloaded and been
 * parsed. Until then the hero paints in a fallback face, and swapping to the
 * real one repaints the text, which is when Largest Contentful Paint is
 * actually recorded. Lighthouse measured that as 2239ms of "render delay" on an
 * element with no load time at all.
 *
 * Preloading has to happen from the HTML head to start those downloads in
 * parallel with the CSS, and the filenames are content-hashed at build time —
 * hence a plugin rather than two hard-coded tags.
 *
 * Only two faces are preloaded, and deliberately: the display face for the
 * headline and the body face for the sub-heading, which is the element
 * Lighthouse selects as LCP. Preloading all seven would have them compete for
 * bandwidth with the one that decides the metric.
 */
function preloadHeroFonts(): Plugin {
  const wanted = [/archivo-latin-700-normal-[^/]*\.woff2$/, /inter-latin-400-normal-[^/]*\.woff2$/];

  return {
    name: "preload-hero-fonts",
    apply: "build",
    enforce: "post",
    transformIndexHtml(html, ctx) {
      if (!ctx.bundle) return html;

      const hrefs = Object.keys(ctx.bundle)
        .filter((file) => wanted.some((pattern) => pattern.test(file)))
        .map((file) => `/${file}`);

      return {
        html,
        tags: hrefs.map((href) => ({
          tag: "link",
          injectTo: "head-prepend" as const,
          attrs: {
            rel: "preload",
            as: "font",
            type: "font/woff2",
            crossorigin: "anonymous",
            href,
          },
        })),
      };
    },
  };
}

export default defineConfig({
  plugins: [react(), preloadHeroFonts()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
  test: {
    // `jsdom` rather than the default node environment: every test here mounts
    // React and asserts on the rendered DOM.
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Excludes vite's default `**/node_modules/**` plus the build output, so a
    // stale `dist` cannot contribute phantom suites.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
