import { useMemo } from "react";

import { SKILL_NODES } from "../content/landing";
import {
  fibonacciSphere,
  LABEL_OFFSETS,
  nodeVectors,
  project,
  sphereCentre,
  sphereRadius,
} from "../lib/constellation";

/** The still is drawn in a fixed coordinate space and scaled to fit. */
const VIEW_W = 1200;
const VIEW_H = 820;

/** Fewer points than the canvas: this is SVG, and every dot is real geometry. */
const STILL_DOTS = 900;
const STILL_STARS = 220;
/** Depth buckets. One `<path>` each, so 900 dots cost four elements. */
const BUCKETS = 4;

/**
 * Deterministic PRNG (mulberry32).
 *
 * The stars must land in the same places on every render. `Math.random()` here
 * would reposition them whenever React re-rendered the hero, which on a page
 * with a sticky nav that updates on scroll is often — and a star-field that
 * reshuffles while you read is unmistakable.
 */
function seeded(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * The constellation, frozen at rotation zero.
 *
 * Shown in three cases: narrow viewports, `prefers-reduced-motion`, and the
 * window before the canvas has painted its first frame. It is the same scene
 * from `lib/constellation.ts` at `angle = 0` — not a second illustration — so
 * the composition a phone gets is the composition a laptop gets, minus the
 * motion.
 *
 * Rendered as a handful of `<path>` elements rather than 900 `<circle>`s: each
 * path is a run of zero-length subpaths with a round line cap, which draws a
 * dot per subpath. Nine hundred circle elements would be nine hundred nodes in
 * the accessibility and layout trees on exactly the devices least able to
 * afford them.
 */
export function ConstellationStill() {
  const scene = useMemo(() => {
    const radius = sphereRadius(VIEW_W, VIEW_H);
    const centre = sphereCentre(VIEW_W, VIEW_H);

    /* --- sphere, bucketed by depth --- */
    const dotPaths: string[] = Array.from({ length: BUCKETS }, () => "");
    for (const dot of fibonacciSphere(STILL_DOTS)) {
      const p = project(dot, 0, centre.x, centre.y, radius);
      const normalised = (p.depth + 1) / 2;
      const bucket = Math.min(BUCKETS - 1, Math.floor(normalised * BUCKETS));
      dotPaths[bucket] += `M${p.x.toFixed(1)} ${p.y.toFixed(1)}h.01`;
    }

    /* --- stars --- */
    const random = seeded(0x51ce);
    let dimStars = "";
    let brightStars = "";
    for (let i = 0; i < STILL_STARS; i += 1) {
      const x = (random() * VIEW_W).toFixed(1);
      const y = (random() * VIEW_H).toFixed(1);
      if (random() < 0.8) dimStars += `M${x} ${y}h.01`;
      else brightStars += `M${x} ${y}h.01`;
    }

    /* --- nodes, back to front, all eight kept --- */
    const nodes = nodeVectors()
      .map((vector, i) => ({ ...project(vector, 0, centre.x, centre.y, radius), i }))
      .sort((a, b) => a.depth - b.depth);

    /*
     * No arcs.
     *
     * An arc is a comet — a moving head with a trail behind it — and a frozen
     * one is just a line across a ball. Drawing the path in full here made the
     * placeholder read as the finished design rather than as the instant before
     * it, which is exactly the impression this frame must not give.
     */
    return { radius, centre, dotPaths, dimStars, brightStars, nodes };
  }, []);

  const labelScale = Math.max(0.75, scene.radius / 300);

  return (
    <svg
      aria-hidden="true"
      className="h-full w-full"
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        {/* Stops mirror `buildAtmosphere` in SkillConstellation.tsx, where the
            gradient runs to 1.85r — so the silhouette sits at 54% and that is
            where the rim light goes. A change to one must be made to the other. */}
        <radialGradient id="gt-atmosphere">
          <stop offset="0%" stopColor="#2563EB" stopOpacity="0.14" />
          <stop offset="34%" stopColor="#2563EB" stopOpacity="0.10" />
          <stop offset="47%" stopColor="#2563EB" stopOpacity="0.24" />
          <stop offset="54%" stopColor="#96C2FF" stopOpacity="0.55" />
          <stop offset="60%" stopColor="#3878FF" stopOpacity="0.32" />
          <stop offset="74%" stopColor="#2563EB" stopOpacity="0.14" />
          <stop offset="88%" stopColor="#2563EB" stopOpacity="0.05" />
          <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
        </radialGradient>
      </defs>

      <path
        d={scene.dimStars}
        stroke="#FFFFFF"
        strokeOpacity="0.14"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path
        d={scene.brightStars}
        stroke="#FFFFFF"
        strokeOpacity="0.3"
        strokeWidth="2"
        strokeLinecap="round"
      />

      <circle
        cx={scene.centre.x}
        cy={scene.centre.y}
        r={scene.radius * 1.85}
        fill="url(#gt-atmosphere)"
      />

      {scene.dotPaths.map((d, bucket) => (
        <path
          key={bucket}
          d={d}
          stroke={bucket >= BUCKETS - 1 ? "#BAD2FF" : "#2563EB"}
          strokeOpacity={0.14 + (bucket / (BUCKETS - 1)) * 0.72}
          strokeWidth={bucket >= BUCKETS / 2 ? 1.6 : 1.2}
          strokeLinecap="round"
        />
      ))}

      {scene.nodes.map((node) => {
        const offset = LABEL_OFFSETS[node.i];
        const lx = node.x + offset.dx * labelScale;
        const ly = node.y + offset.dy * labelScale;
        const text = SKILL_NODES[node.i].toUpperCase();
        // Monospace, so a character count is an accurate width. Measuring text
        // is not available before paint, and this has to be right on the first
        // frame — it is the frame that exists to be fast.
        const boxWidth = text.length * 7.25 + 18;
        const boxHeight = 24;
        const boxX = offset.dx < 0 ? lx - boxWidth : lx;
        // The marker carries the depth cue; the label does not. Matches the
        // canvas, where fading labels by depth was the bug that made the two
        // rear nodes look like they were rendering behind the mesh.
        const markerOpacity = 0.25 + Math.min(1, (node.depth + 1) / 1.2) * 0.75;

        return (
          <g key={node.i}>
            <line
              x1={node.x}
              y1={node.y}
              x2={lx}
              y2={ly}
              stroke="#FFFFFF"
              strokeOpacity={0.34 * markerOpacity}
            />
            <circle
              cx={node.x}
              cy={node.y}
              r={2.4 * node.scale}
              fill="#E2ECFF"
              fillOpacity={0.95 * markerOpacity}
            />
            <rect
              x={boxX}
              y={ly - boxHeight / 2}
              width={boxWidth}
              height={boxHeight}
              rx="5"
              fill="#080C1A"
              fillOpacity="0.94"
              stroke="#FFFFFF"
              strokeOpacity="0.28"
            />
            <text
              x={boxX + 9}
              y={ly + 4}
              fill="#FFFFFF"
              fillOpacity="0.97"
              fontFamily='"JetBrains Mono", ui-monospace, monospace'
              fontSize="12"
              fontWeight="500"
            >
              {text}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
