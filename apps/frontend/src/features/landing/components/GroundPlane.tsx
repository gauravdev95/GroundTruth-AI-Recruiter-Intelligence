import { useEffect, useRef } from "react";

import { subscribeFrame } from "@/design/motion";

/* ==================================================================
   TUNING
   ================================================================== */

/** Focal length in pixels. Larger is a longer lens — a flatter recession. */
const FOCAL = 300;
/** How far the eye floats above the plane, in world units. */
const CAM_HEIGHT = 52;

/** Grid resolution. 26 x 44 is 1,144 intersections, all of them dots. */
const ROWS = 26;
const COLS = 44;
/** World-space gap between rows and between columns. */
const ROW_GAP = 11;
const COL_GAP = 9;
/** Nearest row's depth. Below this the perspective divide explodes. */
const Z_NEAR = 13;

/** World units per second the grid drifts toward the viewer. */
const DRIFT = 5.2;

/** Alpha buckets for the intersection dots — six fills for 1,144 points. */
const DOT_BUCKETS = 6;

/**
 * Ceiling on the whole scene's opacity.
 *
 * This sits behind a line of copy and must lose to it every time. Everything
 * below is multiplied by this, so there is exactly one number to turn down if
 * the plane ever starts competing with the text.
 */
const MAX_ALPHA = 0.5;

const ELECTRIC = "37, 99, 235";

interface Point {
  x: number;
  y: number;
  /** Already includes depth, edge and global falloff. */
  alpha: number;
  /** True where the point is in front of the eye and worth drawing. */
  ok: boolean;
}

/**
 * A slowly undulating wireframe ground plane, receding to a horizon.
 *
 * WHY IT IS HERE. The section it backs is the first thing under the hero, and
 * the product is called GroundTruth. The hero gives you the sphere; this gives
 * you the ground, in the same electric blue and the same dotted-mesh language,
 * so the two read as one world rather than as a rendered hero followed by a
 * plain black strip.
 *
 * HOW THE PERSPECTIVE WORKS. One divide, no matrices. A point at world
 * `(wx, wy, wz)` lands at `horizon + FOCAL * (CAM_HEIGHT - wy) / wz`, so as
 * `wz` grows the point climbs asymptotically toward the horizon line and the
 * grid converges on its own. Rows march toward the viewer by decreasing `wz`
 * over time and wrapping, which is what makes the plane drift without the
 * camera moving.
 *
 * The surface is not flat: a pair of long-period sines displaces `wy`, so the
 * grid breathes like terrain instead of sliding like a floor. Both periods are
 * deliberately slow and mutually prime enough that the motion never visibly
 * repeats.
 *
 * COST. 1,144 projections a frame. The intersection dots are bucketed by alpha
 * and drawn in six fills — the same trick the hero's sphere uses — and the
 * wireframe is one polyline per row plus every second column, so the whole
 * scene is well under a hundred draw calls.
 *
 * Like the hero, this runs regardless of `prefers-reduced-motion`; see the note
 * in Hero.tsx. It is decorative, `aria-hidden`, and the motion is slower here
 * than anywhere else on the page.
 */
export function GroundPlane() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let horizonY = 0;

    let sceneTime = 0;
    let lastFrame = 0;

    /* One row of points, reused; the grid is walked row by row. */
    const grid: Point[][] = Array.from({ length: ROWS }, () =>
      Array.from({ length: COLS }, () => ({ x: 0, y: 0, alpha: 0, ok: false })),
    );
    const buckets: number[][] = Array.from({ length: DOT_BUCKETS }, () => []);

    function resize() {
      const rect = canvas!.getBoundingClientRect();
      dpr = Math.min(2, window.devicePixelRatio || 1);
      width = rect.width;
      height = rect.height;

      canvas!.width = Math.max(1, Math.floor(width * dpr));
      canvas!.height = Math.max(1, Math.floor(height * dpr));
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      // The horizon sits above the top edge, not inside the frame. A visible
      // vanishing point would draw the eye to a hard line right where the copy
      // is; pushing it off-canvas keeps only the near, open part of the plane.
      horizonY = -height * 0.35;
    }

    resize();

    /** Terrain height at a world position. Two slow sines, no noise table. */
    function surface(wx: number, wz: number, time: number): number {
      return Math.sin(wx * 0.031 + time * 0.33) * 3.4 + Math.sin(wz * 0.043 - time * 0.21) * 2.7;
    }

    function buildGrid(time: number) {
      const span = ROWS * ROW_GAP;
      // Rows march toward the eye and wrap. Computed from `time` rather than
      // accumulated, so a dropped frame cannot desynchronise the grid.
      const drift = (time * DRIFT) % ROW_GAP;

      for (let r = 0; r < ROWS; r += 1) {
        const wz = Z_NEAR + r * ROW_GAP - drift;
        const row = grid[r];

        // Fade with distance, and again as a row nears the far edge so the
        // grid dissolves instead of ending on a hard line.
        const t = (wz - Z_NEAR) / span;
        const depthFade = Math.max(0, 1 - t) * Math.max(0, 1 - t * t * 0.9);

        for (let c = 0; c < COLS; c += 1) {
          const wx = (c - (COLS - 1) / 2) * COL_GAP;
          const wy = surface(wx, wz, time);
          const point = row[c];

          if (wz <= 1) {
            point.ok = false;
            continue;
          }

          point.x = width / 2 + (FOCAL * wx) / wz;
          point.y = horizonY + (FOCAL * (CAM_HEIGHT - wy)) / wz;

          // Fade toward the left and right extremes, so the plane has no cut
          // edges — it should read as continuing past the viewport.
          const acrossness = Math.abs(c - (COLS - 1) / 2) / ((COLS - 1) / 2);
          const edgeFade = Math.max(0, 1 - acrossness * acrossness);

          point.alpha = depthFade * edgeFade * MAX_ALPHA;
          point.ok = point.y > -height && point.y < height * 2;
        }
      }
    }

    function drawWireframe() {
      ctx!.lineCap = "round";

      /* Rows — one polyline each, alpha constant along the row. */
      for (let r = 0; r < ROWS; r += 1) {
        const row = grid[r];
        const alpha = row[Math.floor(COLS / 2)].alpha;
        if (alpha < 0.012) continue;

        // The nearest rows get an additive halo under the line. Only the near
        // ones: far rows are a pixel apart and their glows would merge into a
        // solid band across the horizon.
        const near = r < 8;

        if (near) {
          ctx!.globalCompositeOperation = "lighter";
          ctx!.strokeStyle = `rgba(${ELECTRIC}, ${alpha * 0.5})`;
          ctx!.lineWidth = 5;
          ctx!.beginPath();
          for (let c = 0; c < COLS; c += 1) {
            const point = row[c];
            if (!point.ok) continue;
            if (c === 0) ctx!.moveTo(point.x, point.y);
            else ctx!.lineTo(point.x, point.y);
          }
          ctx!.stroke();
          ctx!.globalCompositeOperation = "source-over";
        }

        ctx!.strokeStyle = `rgba(96, 150, 255, ${alpha * 0.85})`;
        ctx!.lineWidth = 1;
        ctx!.beginPath();
        for (let c = 0; c < COLS; c += 1) {
          const point = row[c];
          if (!point.ok) continue;
          if (c === 0) ctx!.moveTo(point.x, point.y);
          else ctx!.lineTo(point.x, point.y);
        }
        ctx!.stroke();
      }

      /* Columns — every second one, so the grid reads without doubling cost. */
      for (let c = 0; c < COLS; c += 2) {
        ctx!.strokeStyle = `rgba(${ELECTRIC}, ${grid[0][c].alpha * 0.5})`;
        ctx!.lineWidth = 1;
        ctx!.beginPath();
        let started = false;
        for (let r = 0; r < ROWS; r += 1) {
          const point = grid[r][c];
          if (!point.ok) continue;
          if (!started) {
            ctx!.moveTo(point.x, point.y);
            started = true;
          } else {
            ctx!.lineTo(point.x, point.y);
          }
        }
        ctx!.stroke();
      }
    }

    function drawDots() {
      for (const bucket of buckets) bucket.length = 0;

      for (let r = 0; r < ROWS; r += 1) {
        for (let c = 0; c < COLS; c += 1) {
          const point = grid[r][c];
          if (!point.ok || point.alpha < 0.02) continue;

          const bucket = Math.min(
            DOT_BUCKETS - 1,
            Math.floor((point.alpha / MAX_ALPHA) * DOT_BUCKETS),
          );
          // Near intersections are larger, which is the only size cue the grid
          // needs — the perspective divide does the rest.
          const size = 1 + (1 - r / ROWS) * 1.4;
          buckets[bucket].push(point.x - size / 2, point.y - size / 2, size);
        }
      }

      for (let b = 0; b < DOT_BUCKETS; b += 1) {
        const bucket = buckets[b];
        if (bucket.length === 0) continue;

        ctx!.globalAlpha = ((b + 0.5) / DOT_BUCKETS) * MAX_ALPHA;
        ctx!.fillStyle = b >= DOT_BUCKETS - 2 ? "rgb(176, 205, 255)" : `rgb(${ELECTRIC})`;
        ctx!.beginPath();
        for (let i = 0; i < bucket.length; i += 3) {
          ctx!.rect(bucket[i], bucket[i + 1], bucket[i + 2], bucket[i + 2]);
        }
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;
    }

    function frame(now: number) {
      const seconds = now / 1000;
      if (!lastFrame) lastFrame = seconds;
      sceneTime += Math.min(0.05, seconds - lastFrame);
      lastFrame = seconds;

      ctx!.clearRect(0, 0, width, height);
      buildGrid(sceneTime);
      drawWireframe();
      drawDots();
    }

    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => resize()) : null;
    observer?.observe(canvas);

    const unsubscribe = subscribeFrame(frame);

    return () => {
      unsubscribe();
      observer?.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className="h-full w-full" />;
}
