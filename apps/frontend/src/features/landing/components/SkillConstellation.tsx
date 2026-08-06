import { useEffect, useRef } from "react";

import { subscribeFrame } from "@/design/motion";

import { SKILL_NODES } from "../content/landing";
import {
  arcPoint,
  fibonacciSphere,
  LABEL_OFFSETS,
  lambert,
  nodeVectors,
  project,
  ROTATION_PERIOD,
  SPHERE_DOTS,
  sphereCentre,
  sphereRadius,
  STAR_COUNT,
} from "../lib/constellation";

/* ==================================================================
   TUNING
   ================================================================== */

/**
 * Seconds between arc launches.
 *
 * Each arc lives for `ARC_DURATION` plus its trail, so this interval is what
 * decides how many are in flight at once: roughly 3.2s of life divided by 1.5s
 * of spacing keeps two or three on screen continuously. Raising it produces
 * visible gaps where the sphere has nothing travelling across it.
 */
const ARC_INTERVAL = 1.5;
/** Seconds an arc takes to travel end to end. */
const ARC_DURATION = 2.4;
/** Fraction of the path the glowing trail covers behind the leading edge. */
const ARC_TRAIL = 0.36;
/** Segments per arc. Below ~20 the curve visibly polygonises at this radius. */
const ARC_SEGMENTS = 34;
/** Seconds a node stays lit after an arc reaches it. */
const PULSE_DURATION = 0.45;

/** Alpha buckets, shared by the sphere's dots and the star-field. */
const DOT_BUCKETS = 8;
const STAR_BUCKETS = 6;

const ELECTRIC = "37, 99, 235";
const EMBER = "255, 107, 53";

/* ==================================================================
   SMALL HELPERS
   ================================================================== */

/** `ctx.roundRect` is recent enough that a Safari 15 visitor would lose the
 *  label boxes entirely. Four `arcTo` calls work everywhere. */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** Hermite smoothstep. Used to fade labels through the silhouette edge. */
function smoothstep(edge0: number, edge1: number, value: number): number {
  const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

interface Star {
  x: number;
  y: number;
  size: number;
  /** Phase offset, so no two stars peak together. */
  phase: number;
  /** Radians per second. Each star breathes at its own rate. */
  speed: number;
}

interface Arc {
  from: number;
  to: number;
  /** Scene time, in seconds, at which this arc launched. */
  startedAt: number;
  /** True once the head has landed and the target pulse has been triggered. */
  landed: boolean;
}

/* ==================================================================
   THE SCENE
   ================================================================== */

/**
 * The hero's rotating skill constellation, drawn to a single 2D canvas.
 *
 * WHAT IT IS. A sphere of 2,500 points with an atmospheric rim glow, eight
 * labelled skill nodes anchored to its surface, orange comet-arcs travelling
 * between them along great circles, and 1,400 independently twinkling stars
 * behind. Everything here animates continuously — there is no state in which
 * this component renders a single static frame.
 *
 * WHY CANVAS AND NOT THREE.JS. React Three Fiber, drei and a postprocessing
 * bloom pass are four dependencies and roughly half a megabyte of JavaScript,
 * in an application with no other use for a 3D engine, to draw what is one
 * rotation and one perspective divide — see `lib/constellation.ts`. Bloom is
 * faked by drawing arcs and node cores twice: once wide and faint, once tight
 * and bright. A real bloom pass would also have blown out the label text, which
 * it must not touch.
 *
 * WHAT MAKES IT CHEAP ENOUGH TO RUN AT 60FPS
 *
 * * Both point clouds are bucketed by alpha and drawn with one `fill()` per
 *   bucket — 2,500 dots cost eight fills, 1,400 twinkling stars cost six. This
 *   is why every star can have its own phase and rate without the field costing
 *   1,400 state changes a frame.
 * * The atmosphere gradient is built on resize, not per frame.
 *   `createRadialGradient` inside a draw loop is the most expensive thing this
 *   API offers.
 * * It runs on the application's shared rAF loop, which already stops itself in
 *   a background tab. Nothing here schedules its own frames.
 */
export function SkillConstellation({ onFirstFrame }: { onFirstFrame?: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    /* ---- scene data, built once ------------------------------------ */

    const dots = fibonacciSphere(SPHERE_DOTS);
    const nodes = nodeVectors();
    /* Per-node drift phase and period, so the labels bob out of step. */
    const drift = nodes.map((_, i) => ({ phase: i * 1.37, period: 4 + (i % 3) }));
    const pulseAt: number[] = nodes.map(() => -Infinity);

    let stars: Star[] = [];
    let atmosphere: CanvasGradient | null = null;
    let rimGlow: CanvasGradient | null = null;

    let width = 0;
    let height = 0;
    let dpr = 1;

    let sceneTime = 0;
    let lastFrame = 0;
    let reportedFirstFrame = false;

    /* Reused between frames so the draw loop allocates nothing. */
    const dotBuckets: number[][] = Array.from({ length: DOT_BUCKETS }, () => []);
    const starBuckets: number[][] = Array.from({ length: STAR_BUCKETS }, () => []);

    /* ---- arcs, pre-warmed ------------------------------------------- */

    function randomPair(): { from: number; to: number } {
      const from = Math.floor(Math.random() * nodes.length);
      let to = Math.floor(Math.random() * nodes.length);
      if (to === from)
        to = (to + 1 + Math.floor(Math.random() * (nodes.length - 1))) % nodes.length;
      return { from, to };
    }

    /*
     * Three arcs already mid-flight at scene time zero.
     *
     * Starting empty and waiting for the scheduler meant the first two seconds
     * of the hero — the two seconds a reader is most likely to actually watch —
     * showed a sphere with nothing happening on it. Negative launch times put
     * each of these at a different point along its path on the very first frame.
     */
    const arcs: Arc[] = [-1.9, -1.1, -0.35].map((offset) => ({
      ...randomPair(),
      startedAt: offset,
      landed: false,
    }));
    let nextArcAt = ARC_INTERVAL;

    /* ---- sizing ----------------------------------------------------- */

    function buildStars() {
      stars = new Array(STAR_COUNT);
      for (let i = 0; i < STAR_COUNT; i += 1) {
        stars[i] = {
          x: Math.random() * width,
          y: Math.random() * height,
          size: Math.random() < 0.86 ? 1.2 : 2,
          phase: Math.random() * Math.PI * 2,
          // 0.25–0.85 rad/s. Slow, and spread widely enough that the field
          // never falls into a visible collective rhythm.
          speed: 0.25 + Math.random() * 0.6,
        };
      }
    }

    /**
     * Two gradients, drawn either side of the dot mesh.
     *
     * `atmosphere` goes down first, under the dots: a wide halo whose bright
     * band sits exactly on the silhouette. The gradient runs to 1.85r, so the
     * sphere's edge is at 1/1.85 = 0.54 of its radius — that is where the rim
     * light goes, and everything past it is atmosphere bleeding outward.
     *
     * `rimGlow` goes on top of the dots in `lighter` composite, which adds
     * rather than covers. That is what makes the edge actually glow instead of
     * merely being a brighter ring painted behind the mesh: the light wraps
     * over the dots at the limb the way an atmosphere does over a horizon.
     * Drawing it underneath was why the previous rim read as flat.
     */
    function buildAtmosphere() {
      const radius = sphereRadius(width, height);
      const centre = sphereCentre(width, height);
      const outer = radius * 1.85;

      const wide = ctx!.createRadialGradient(centre.x, centre.y, 0, centre.x, centre.y, outer);
      wide.addColorStop(0, `rgba(${ELECTRIC}, 0.14)`);
      wide.addColorStop(0.34, `rgba(${ELECTRIC}, 0.1)`);
      wide.addColorStop(0.47, `rgba(${ELECTRIC}, 0.24)`);
      wide.addColorStop(0.54, "rgba(150, 194, 255, 0.55)");
      wide.addColorStop(0.6, "rgba(56, 120, 255, 0.32)");
      wide.addColorStop(0.74, `rgba(${ELECTRIC}, 0.14)`);
      wide.addColorStop(0.88, `rgba(${ELECTRIC}, 0.05)`);
      wide.addColorStop(1, `rgba(${ELECTRIC}, 0)`);
      atmosphere = wide;

      const rim = ctx!.createRadialGradient(
        centre.x,
        centre.y,
        radius * 0.8,
        centre.x,
        centre.y,
        radius * 1.42,
      );
      rim.addColorStop(0, `rgba(${ELECTRIC}, 0)`);
      rim.addColorStop(0.34, "rgba(120, 172, 255, 0.34)");
      rim.addColorStop(0.5, "rgba(70, 132, 255, 0.2)");
      rim.addColorStop(0.72, `rgba(${ELECTRIC}, 0.08)`);
      rim.addColorStop(1, `rgba(${ELECTRIC}, 0)`);
      rimGlow = rim;
    }

    function resize() {
      const rect = canvas!.getBoundingClientRect();
      // Capped at 2: a 3x phone screen triples the fill cost of every dot for a
      // difference nobody can see on 1px rectangles.
      dpr = Math.min(2, window.devicePixelRatio || 1);
      width = rect.width;
      height = rect.height;

      canvas!.width = Math.max(1, Math.floor(width * dpr));
      canvas!.height = Math.max(1, Math.floor(height * dpr));
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      buildStars();
      buildAtmosphere();
    }

    resize();

    /* ---- drawing ---------------------------------------------------- */

    /**
     * The whole star-field, every star on its own twinkle.
     *
     * Alpha oscillates between 0.1 and 0.3 — the brief's range — at each star's
     * own rate and phase. Bucketing by alpha is what makes that affordable:
     * six `fill()` calls for 1,400 independently animating points.
     */
    function drawStars(time: number) {
      for (const bucket of starBuckets) bucket.length = 0;

      for (const star of stars) {
        const wave = 0.5 + 0.5 * Math.sin(time * star.speed + star.phase);
        const alpha = 0.1 + wave * 0.2;
        const bucket = Math.min(
          STAR_BUCKETS - 1,
          Math.max(0, Math.floor(((alpha - 0.1) / 0.2) * STAR_BUCKETS)),
        );
        starBuckets[bucket].push(star.x, star.y, star.size);
      }

      ctx!.fillStyle = "#FFFFFF";
      for (let b = 0; b < STAR_BUCKETS; b += 1) {
        const bucket = starBuckets[b];
        if (bucket.length === 0) continue;

        ctx!.globalAlpha = 0.1 + ((b + 0.5) / STAR_BUCKETS) * 0.2;
        ctx!.beginPath();
        for (let i = 0; i < bucket.length; i += 3) {
          ctx!.rect(bucket[i], bucket[i + 1], bucket[i + 2], bucket[i + 2]);
        }
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;
    }

    function drawDots(
      angle: number,
      time: number,
      centreX: number,
      centreY: number,
      radius: number,
    ) {
      for (const bucket of dotBuckets) bucket.length = 0;

      for (let i = 0; i < dots.length; i += 1) {
        const p = project(dots[i], angle, centreX, centreY, radius);

        // Depth to brightness. The far hemisphere stays faintly visible rather
        // than being culled — seeing through the sphere is what tells the eye
        // it is a shell of points and not a printed disc.
        const depthTerm = 0.1 + smoothstep(-1, 1, p.depth) * 0.62;

        /*
         * Directional shading — the thing that turns this from a disc into a
         * volume.
         *
         * Depth alone lights the whole near hemisphere evenly, which is
         * precisely what a flat disc of dots looks like. A Lambert term against
         * a fixed light puts a bright pole up and to the left and runs a
         * terminator across the surface, so the eye reads curvature. The floor
         * of 0.3 keeps the unlit side present rather than black — this is a
         * point cloud, not an opaque planet, and dots that vanish entirely
         * would take the silhouette with them.
         */
        const shade = 0.3 + lambert(p.normal) * 0.82;

        let alpha = Math.min(1, depthTerm * shade * 1.5);

        // A slow wander plus a rare flare, so a random-looking subset lifts
        // every few seconds without any per-dot state to keep.
        alpha *= 0.8 + 0.2 * Math.sin(time * 0.6 + i * 0.7);
        if (Math.sin(time * 0.25 + i * 2.399) > 0.9994) alpha = Math.min(1, alpha * 2.6);

        const bucket = Math.min(DOT_BUCKETS - 1, Math.max(0, Math.floor(alpha * DOT_BUCKETS)));
        // Lit dots are also fractionally larger. Real specular falloff would
        // change brightness only, but at 1–2px a size step reads as brightness
        // the eye can actually resolve.
        const size = (p.depth > 0 ? 1.5 + shade * 0.5 : 1.15) * p.scale;

        dotBuckets[bucket].push(p.x - size / 2, p.y - size / 2, size);
      }

      for (let b = 0; b < DOT_BUCKETS; b += 1) {
        const bucket = dotBuckets[b];
        if (bucket.length === 0) continue;

        ctx!.globalAlpha = (b + 0.5) / DOT_BUCKETS;
        /*
         * Three tiers, not two. The brightest dots are near-white where the
         * light hits, the middle band is a lifted blue, and the dimmest stay
         * saturated electric. A single colour across the whole mesh flattens
         * the shading back out — the ramp is doing as much work as the alpha.
         */
        ctx!.fillStyle =
          b >= DOT_BUCKETS - 2
            ? "rgb(214, 230, 255)"
            : b >= DOT_BUCKETS - 4
              ? "rgb(120, 165, 245)"
              : `rgb(${ELECTRIC})`;
        ctx!.beginPath();
        for (let i = 0; i < bucket.length; i += 3) {
          ctx!.rect(bucket[i], bucket[i + 1], bucket[i + 2], bucket[i + 2]);
        }
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;
    }

    /**
     * The comet arcs.
     *
     * Each is a leading head with a trail fading out behind it, redrawn every
     * frame from the head's current position along the path — never a completed
     * line. Segments outside the trail window are skipped entirely, which is
     * what makes the tail *end* rather than fade to an almost-invisible full
     * stroke.
     */
    function drawArcs(angle: number, centreX: number, centreY: number, radius: number) {
      ctx!.lineCap = "round";

      for (const arc of arcs) {
        const head = Math.min(1, (sceneTime - arc.startedAt) / ARC_DURATION);
        if (head < 0) continue;

        const from = nodes[arc.from];
        const to = nodes[arc.to];

        for (let s = 0; s < ARC_SEGMENTS; s += 1) {
          const t0 = s / ARC_SEGMENTS;
          const t1 = (s + 1) / ARC_SEGMENTS;

          // Distance back from the head, as a fraction of the trail length.
          const behind = (head - t1) / ARC_TRAIL;
          if (behind < 0 || behind > 1) continue;

          const a = project(arcPoint(from, to, t0), angle, centreX, centreY, radius);
          const b = project(arcPoint(from, to, t1), angle, centreX, centreY, radius);

          /*
           * Brightness along the trail.
           *
           * `1 - behind` on its own faded the tail out linearly and the whole
           * trace read as faint. The curve now holds near full brightness for
           * the first half of the trail and drops away over the second, so the
           * arc is unmistakable at a glance and still ends as a comet rather
           * than a uniform stroke. The 0.35 floor keeps even the tail visible.
           */
          const along = 1 - behind;
          const fade = 0.35 + 0.65 * along * along * (3 - 2 * along);
          // Behind the sphere the trace dims instead of vanishing, which is
          // what sells the arc as travelling *around* a solid object.
          const occlusion = a.depth > 0 ? 1 : 0.3;
          const alpha = fade * occlusion;
          if (alpha < 0.02) continue;

          // Three passes stand in for a bloom: a wide additive halo, a mid
          // spread, then the bright core. `lighter` on the halo is what makes
          // it read as light rather than as a thicker orange line.
          ctx!.globalCompositeOperation = "lighter";
          ctx!.strokeStyle = `rgba(${EMBER}, ${alpha * 0.3})`;
          ctx!.lineWidth = 15;
          ctx!.beginPath();
          ctx!.moveTo(a.x, a.y);
          ctx!.lineTo(b.x, b.y);
          ctx!.stroke();

          ctx!.strokeStyle = `rgba(${EMBER}, ${alpha * 0.5})`;
          ctx!.lineWidth = 6.5;
          ctx!.beginPath();
          ctx!.moveTo(a.x, a.y);
          ctx!.lineTo(b.x, b.y);
          ctx!.stroke();
          ctx!.globalCompositeOperation = "source-over";

          ctx!.strokeStyle = `rgba(255, 150, 100, ${alpha})`;
          ctx!.lineWidth = 3.2;
          ctx!.beginPath();
          ctx!.moveTo(a.x, a.y);
          ctx!.lineTo(b.x, b.y);
          ctx!.stroke();
        }

        /* The head itself — a bright point at the front of the trail. */
        if (head < 1) {
          const tip = project(arcPoint(from, to, head), angle, centreX, centreY, radius);
          if (tip.depth > 0) {
            ctx!.globalCompositeOperation = "lighter";
            ctx!.fillStyle = `rgba(${EMBER}, 0.4)`;
            ctx!.beginPath();
            ctx!.arc(tip.x, tip.y, 12 * tip.scale, 0, Math.PI * 2);
            ctx!.fill();
            ctx!.globalCompositeOperation = "source-over";

            ctx!.fillStyle = "rgba(255, 226, 208, 0.98)";
            ctx!.beginPath();
            ctx!.arc(tip.x, tip.y, 3 * tip.scale, 0, Math.PI * 2);
            ctx!.fill();
          }
        }
      }
    }

    /**
     * The eight skill nodes and their labels.
     *
     * EVERY LABEL IS OPAQUE, ALWAYS, AND ALWAYS IN FRONT.
     *
     * This used to multiply each label's alpha by a depth term and skip the
     * label entirely below a threshold, which is why the two nodes furthest
     * round the back — REACT and DISTRIBUTED SYSTEMS at most rotations — faded
     * to nothing and looked like a z-fighting bug. They were not behind the
     * mesh; they were being drawn at almost zero alpha on purpose. The depth
     * cue now lives entirely in the *marker and its connector*, which do still
     * dim round the back, while the label itself is chrome: it sits on top of
     * the scene at full opacity so all eight technologies are always readable.
     *
     * The layout runs in three passes because it has to: positions for all
     * eight are needed before any collision between them can be resolved, and
     * nothing can be drawn until the collisions are settled.
     */
    function drawNodes(
      angle: number,
      time: number,
      centreX: number,
      centreY: number,
      radius: number,
    ) {
      const labelSize = width < 1100 ? 11 : 12;
      ctx!.font = `500 ${labelSize}px "JetBrains Mono", ui-monospace, monospace`;
      ctx!.textBaseline = "middle";

      const padX = 9;
      const padY = 6;
      const boxHeight = labelSize + padY * 2;

      /* ---- pass 1: where each label wants to be -------------------- */

      const placed = nodes.map((node, i) => {
        const p = project(node, angle, centreX, centreY, radius);
        const bob = Math.sin((time / drift[i].period) * Math.PI * 2 + drift[i].phase) * 2.5;
        /*
         * The offset scales with the perspective divide, not just the sphere's
         * size. That is what anchors the label to its point: a node on the near
         * face pushes its label further out than one near the rim, so the label
         * travels with the surface instead of sliding on a flat plane in front.
         */
        const anchor = Math.max(0.7, (radius / 300) * p.scale);
        const text = SKILL_NODES[i].toUpperCase();
        const boxWidth = ctx!.measureText(text).width + padX * 2;

        const lx = p.x + LABEL_OFFSETS[i].dx * anchor;
        const ly = p.y + LABEL_OFFSETS[i].dy * anchor + bob;

        return {
          i,
          p,
          text,
          // Anchor the box on the side the offset points, so a label to the
          // left of its node grows leftward rather than back across the node.
          x: LABEL_OFFSETS[i].dx < 0 ? lx - boxWidth : lx,
          y: ly - boxHeight / 2,
          w: boxWidth,
          h: boxHeight,
        };
      });

      /* ---- pass 2: push overlapping boxes apart -------------------- */

      /*
       * Relaxation, not a solver. Six passes over 28 pairs is nothing per
       * frame, and the result is stable enough that boxes do not jitter as the
       * sphere turns — each frame starts from the same desired positions and
       * converges the same way, so there is no feedback between frames.
       *
       * Separation is vertical only. Moving a label sideways detaches it from
       * the side of the node its connector leaves from, which looks far worse
       * than two labels sitting a little above and below each other.
       */
      const GAP = 6;
      for (let pass = 0; pass < 6; pass += 1) {
        for (let a = 0; a < placed.length; a += 1) {
          for (let b = a + 1; b < placed.length; b += 1) {
            const boxA = placed[a];
            const boxB = placed[b];

            const overlapX = Math.min(boxA.x + boxA.w, boxB.x + boxB.w) - Math.max(boxA.x, boxB.x);
            if (overlapX <= 0) continue;

            const overlapY =
              Math.min(boxA.y + boxA.h, boxB.y + boxB.h) - Math.max(boxA.y, boxB.y) + GAP;
            if (overlapY <= 0) continue;

            const push = overlapY / 2;
            if (boxA.y < boxB.y) {
              boxA.y -= push;
              boxB.y += push;
            } else {
              boxA.y += push;
              boxB.y -= push;
            }
          }
        }
      }

      /* Keep every box inside the canvas — a label pushed off the top edge is
         no more readable than one faded to zero. */
      for (const box of placed) {
        box.x = Math.min(Math.max(box.x, 10), Math.max(10, width - box.w - 10));
        box.y = Math.min(Math.max(box.y, 10), Math.max(10, height - box.h - 10));
      }

      /* ---- pass 3: markers and connectors, back to front ----------- */

      for (const box of [...placed].sort((a, b) => a.p.depth - b.p.depth)) {
        const { i, p } = box;
        // The marker keeps the depth cue the label gave up. Floored at 0.25 so
        // a node round the back still shows where its label is pointing.
        const depthFade = 0.25 + smoothstep(-1, 0.2, p.depth) * 0.75;

        const pulse = Math.max(0, 1 - (sceneTime - pulseAt[i]) / PULSE_DURATION);
        // Ease the pulse out; a linear decay reads as a light switch.
        const glow = pulse * pulse;

        /* connector — from the node to the near edge of its label box */
        const targetX = box.x + box.w / 2 < p.x ? box.x + box.w : box.x;
        const targetY = box.y + box.h / 2;
        ctx!.strokeStyle = `rgba(255, 255, 255, ${0.34 * depthFade})`;
        ctx!.lineWidth = 1;
        ctx!.beginPath();
        ctx!.moveTo(p.x, p.y);
        ctx!.lineTo(targetX, targetY);
        ctx!.stroke();

        /* node marker, seated on the surface with a faint ring around it */
        const markerRadius = (2.3 + glow * 3.4) * p.scale;

        if (glow > 0.01) {
          ctx!.globalCompositeOperation = "lighter";
          ctx!.fillStyle = `rgba(${EMBER}, ${0.45 * glow})`;
          ctx!.beginPath();
          ctx!.arc(p.x, p.y, markerRadius * 3.6, 0, Math.PI * 2);
          ctx!.fill();
          ctx!.globalCompositeOperation = "source-over";
        }

        ctx!.strokeStyle = `rgba(150, 190, 255, ${0.4 * depthFade})`;
        ctx!.lineWidth = 1;
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, markerRadius * 2.1, 0, Math.PI * 2);
        ctx!.stroke();

        ctx!.fillStyle =
          glow > 0.05 ? `rgba(255, 150, 100, 1)` : `rgba(226, 236, 255, ${0.95 * depthFade})`;
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, markerRadius, 0, Math.PI * 2);
        ctx!.fill();
      }

      /* ---- pass 4: the label boxes, on top, fully opaque ----------- */

      for (const box of placed) {
        roundRect(ctx!, box.x, box.y, box.w, box.h, 5);
        // Near-solid, not the 0.8 the brief suggested: these now sit over the
        // lit face of the sphere as often as over empty space, and a
        // translucent box lets the dot mesh read straight through the letters.
        ctx!.fillStyle = "rgba(8, 12, 26, 0.94)";
        ctx!.fill();
        ctx!.strokeStyle = "rgba(255, 255, 255, 0.28)";
        ctx!.lineWidth = 1;
        ctx!.stroke();

        ctx!.fillStyle = "rgba(255, 255, 255, 0.97)";
        ctx!.fillText(box.text, box.x + padX, box.y + box.h / 2 + 0.5);
      }
    }

    /* ---- arc scheduling --------------------------------------------- */

    function updateArcs() {
      if (sceneTime >= nextArcAt) {
        arcs.push({ ...randomPair(), startedAt: sceneTime, landed: false });
        // Jittered, so the arcs never fall into a visible metronome.
        nextArcAt = sceneTime + ARC_INTERVAL * (0.75 + Math.random() * 0.5);
      }

      for (let i = arcs.length - 1; i >= 0; i -= 1) {
        const arc = arcs[i];
        const age = sceneTime - arc.startedAt;

        // The verification moment: the head reaches the target and lights it.
        if (!arc.landed && age >= ARC_DURATION) {
          arc.landed = true;
          pulseAt[arc.to] = sceneTime;
        }
        // Retire it once the trail has finished passing the endpoint.
        if (age > ARC_DURATION * (1 + ARC_TRAIL) + 0.2) arcs.splice(i, 1);
      }
    }

    /* ---- the frame -------------------------------------------------- */

    function frame(now: number) {
      const seconds = now / 1000;
      if (!lastFrame) lastFrame = seconds;
      // Clamped: a tab restored after a minute must not advance the scene by a
      // minute in one step, which would teleport the rotation and fire a
      // backlog of arcs at once.
      const delta = Math.min(0.05, seconds - lastFrame);
      lastFrame = seconds;
      sceneTime += delta;

      const radius = sphereRadius(width, height);
      const centre = sphereCentre(width, height);
      const angle = (sceneTime / ROTATION_PERIOD) * Math.PI * 2;

      updateArcs();

      ctx!.clearRect(0, 0, width, height);
      drawStars(sceneTime);

      if (atmosphere) {
        ctx!.fillStyle = atmosphere;
        ctx!.fillRect(0, 0, width, height);
      }

      drawDots(angle, sceneTime, centre.x, centre.y, radius);

      // Over the mesh, additively — the limb light wraps the dots at the edge
      // rather than sitting behind them. See `buildAtmosphere`.
      if (rimGlow) {
        ctx!.globalCompositeOperation = "lighter";
        ctx!.fillStyle = rimGlow;
        ctx!.fillRect(0, 0, width, height);
        ctx!.globalCompositeOperation = "source-over";
      }

      drawArcs(angle, centre.x, centre.y, radius);
      drawNodes(angle, sceneTime, centre.x, centre.y, radius);

      if (!reportedFirstFrame) {
        reportedFirstFrame = true;
        onFirstFrame?.();
      }
    }

    /* ---- wiring ----------------------------------------------------- */

    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => resize()) : null;
    observer?.observe(canvas);

    const unsubscribe = subscribeFrame(frame);

    return () => {
      unsubscribe();
      observer?.disconnect();
    };
  }, [onFirstFrame]);

  return <canvas ref={canvasRef} aria-hidden="true" className="h-full w-full" />;
}
