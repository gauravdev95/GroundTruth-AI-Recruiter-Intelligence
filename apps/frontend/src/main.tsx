import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted, latin-subset only, `display: swap` baked into each file. These
// replace the render-blocking Google Fonts @import the landing stylesheet used
// to carry, so no third-party request sits in front of first paint.
import "@fontsource/archivo/latin-600.css";
import "@fontsource/archivo/latin-700.css";
// The landing page's display face, and the only weight of it that ships: every
// element set in Space Grotesk is set at 700. Loading 400/500 as well would put
// two more faces in front of first paint for weights nothing asks for.
import "@fontsource/space-grotesk/latin-700.css";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-500.css";

/*
 * The application design system. This has to be imported for the product to
 * have a palette at all: `design/Surface.tsx`, `design/primitives.tsx` and
 * every migrated screen are written against `var(--panel)`, `var(--ink)`,
 * `var(--r-lg)` and friends, and an undefined custom property does not fall
 * back to anything — it makes the whole declaration invalid, so a card whose
 * tokens are missing renders transparent, square and bordered in its own text
 * colour rather than visibly broken.
 *
 * Imported before `App` so the tokens are defined ahead of any feature
 * stylesheet the route graph pulls in. That ordering is a convenience, not a
 * correctness requirement — `landing.css` scopes itself with `:has()` so it
 * outranks this file on the landing route regardless of which lands first.
 */
import "./design/tokens.css";

import App from "./app/App";
import "./styles/index.css";

/*
 * The hero's two font faces are preloaded from the HTML head by the
 * `preload-hero-fonts` plugin in vite.config.ts. Doing it here instead was
 * measurably useless: this module only runs once the bundle has been parsed,
 * which is well after the stylesheet has already triggered the font requests.
 */

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
