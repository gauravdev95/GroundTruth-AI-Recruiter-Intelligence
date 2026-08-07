/**
 * The chart palette, as CSS custom properties rather than hex literals.
 *
 * ## Why `var(--…)` and not a colour constant
 *
 * These strings are handed to Recharts, which forwards them to SVG `stroke`
 * and `fill`. Those are presentation attributes — CSS properties in attribute
 * position — so `var()` resolves in them exactly as it does in a stylesheet.
 * That is what makes the charts follow `[data-theme]` for free.
 *
 * The alternative is reading the computed value off the document in an effect
 * and re-rendering on theme change: more code, a frame of stale colour, and a
 * second place the palette lives. Recharts only needs a literal in the sense
 * that it needs a *string*; it never parses it.
 *
 * ## Why `--blue` and not `gt-electric`
 *
 * The charts used #2563EB, which is `gt-electric` — a landing-page token,
 * reachable from the app only under the one sanctioned crossing documented in
 * `tailwind.config.ts` (recruiter surfaces and the match-score band). Charts
 * are neither. More decisively, `gt-electric` is a fixed hex with no light
 * variant: on `--surface` #FFFFFF it is the same value it is on #0B0F1C, so a
 * theme-aware chart cannot be built on it at all. `--blue` is the app's accent
 * and is re-stepped per theme (#2D8CFF dark / #1F6FD8 light).
 *
 * ## The two-series pair, validated rather than assumed
 *
 * `SERIES` is the measured value; `BENCHMARK` is what it is measured against.
 * They are deliberately not two categorical hues — see `SkillRadar`'s
 * docstring for why violet-vs-blue was rejected (ΔE 0.4 under deuteranopia)
 * and why the requirement profile is drawn as a reference line instead.
 *
 * Checked with the palette validator against `--panel-solid` in each theme:
 *
 *   dark  #2D8CFF ↔ #94A3C4   ΔE 15.7 normal · 13.1 protan · 8.9 tritan
 *   light #1F6FD8 ↔ #4A5878   ΔE 15.4 normal · 15.3 deutan · 13.1 tritan
 *
 * Both clear the normal-vision floor of 15 and sit above the 8-point CVD
 * floor, and identity is additionally carried by the dash pattern, so the pair
 * survives greyscale and forced-colours mode. The validator also reports
 * BENCHMARK as failing its lightness-band and chroma-floor checks — correctly,
 * and by design: those two checks ask "is this a distinct categorical hue",
 * and the whole point of a benchmark is that it is not one.
 */
export const CHART = {
  /** The measured series. */
  series: "var(--blue)",
  /** The reference the series is read against. Always dashed, never filled. */
  benchmark: "var(--slate)",
  /** Grid, polar web, and the tooltip cursor. Recessive by rule. */
  grid: "var(--rule)",
  /** Axis tick labels. Text tokens, never the series colour. */
  tick: "var(--muted)",
  /**
   * The ring drawn around an active dot so it separates from the line it sits
   * on. Matches the surface beneath the chart rather than being white, which
   * is the difference between a 2px gap and a 2px white pip on a dark panel.
   */
  markRing: "var(--panel-solid)",
} as const;

/**
 * Recharts' `<Tooltip>` styling, shared so the three charts cannot drift.
 *
 * `backgroundColor` is not optional: Recharts writes an inline `background:
 * #fff` on the tooltip wrapper, so a tooltip that only sets a border renders
 * as a white card on a dark page.
 */
export const CHART_TOOLTIP = {
  contentStyle: {
    backgroundColor: "var(--panel-raised)",
    borderRadius: 8,
    border: "1px solid var(--rule)",
    boxShadow: "var(--shadow-raised)",
    fontSize: 11,
    padding: "4px 8px",
  },
  labelStyle: { color: "var(--slate)" },
  itemStyle: { color: "var(--ink)" },
} as const;
