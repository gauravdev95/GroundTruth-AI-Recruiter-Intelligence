/**
 * Geometry for the hero's skill constellation.
 *
 * Shared by the animated canvas and the static SVG fallback, which is the whole
 * reason it is a module rather than code inside the canvas component: the
 * fallback has to be the *same composition* frozen, not a second drawing that
 * approximates it. A reader on a phone and a reader on a laptop should recognise
 * the same object.
 *
 * There is no 3D library behind this. The scene is a sphere of points, eight
 * labelled nodes on its surface, and arcs between them — one rotation axis, one
 * perspective divide. Adding three.js and its React bindings to render that
 * would have cost roughly half a megabyte to draw a few thousand rectangles.
 */

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

/** A point after projection to the screen. */
export interface Projected {
  x: number;
  y: number;
  /** Perspective scale at this depth. Sizes are multiplied by it. */
  scale: number;
  /** Rotated depth, -1 (far) to 1 (near). Drives alpha and draw order. */
  depth: number;
  /**
   * The rotated unit position, which on a unit sphere is also the surface
   * normal at that point. Kept so the draw loop can shade the mesh without
   * repeating the rotation.
   */
  normal: Vec3;
}

/* ==================================================================
   CONSTANTS
   ================================================================== */

/**
 * Points on the sphere's surface.
 *
 * The draw loop buckets these into eight alpha groups and issues eight fills,
 * so the per-frame cost is dominated by the 2,500 `rect()` calls that build the
 * paths, not by state changes. Density is what gives the sphere mass — at half
 * this count it reads as scattered points rather than a surface.
 */
export const SPHERE_DOTS = 2500;

/**
 * Background stars. Every one of them twinkles, on the same bucketing trick as
 * the sphere's dots — so the whole field animates for about eight fill calls
 * rather than one per star.
 */
export const STAR_COUNT = 1400;

/** Seconds for one full revolution. Slow enough to read as ambient. */
export const ROTATION_PERIOD = 40;

/**
 * Camera tilt, radians. A sphere viewed dead-on has no visible axis and reads
 * as a flat disc of dots; tipping it forward slightly is what makes the point
 * distribution legible as a surface.
 */
export const TILT = -0.28;

/** Distance from the eye to the sphere's centre, in sphere radii. */
export const FOCAL = 2.9;

/**
 * Where each skill sits, as longitude/latitude in radians.
 *
 * Hand-placed rather than distributed evenly. Even spacing puts two labels on
 * the silhouette edge at the same moment, where their boxes collide with the
 * sphere's rim and with each other; these are spread so that at any rotation
 * roughly half are comfortably on the near face.
 *
 * Order matches `SKILL_NODES` in `content/landing.ts`.
 */
export const NODE_POSITIONS: { lon: number; lat: number }[] = [
  { lon: -0.55, lat: 0.62 }, // React
  { lon: 0.42, lat: 0.24 }, // PostgreSQL
  { lon: -1.35, lat: -0.08 }, // System design
  { lon: 1.15, lat: -0.46 }, // Rust
  { lon: -0.25, lat: -0.72 }, // ML Ops
  { lon: 2.15, lat: 0.18 }, // Distributed systems
  { lon: -2.15, lat: 0.48 }, // TypeScript
  { lon: 2.8, lat: -0.38 }, // Go
];

/**
 * Which side of its node each label sits on, and how far.
 *
 * In screen pixels at a reference sphere radius, scaled with the sphere. They
 * alternate left and right so that two nodes drifting past each other push
 * their labels apart rather than stacking them.
 */
export const LABEL_OFFSETS: { dx: number; dy: number }[] = [
  { dx: 26, dy: -30 },
  { dx: 30, dy: -18 },
  { dx: -30, dy: -26 },
  { dx: 28, dy: 24 },
  { dx: -28, dy: 30 },
  { dx: 32, dy: -14 },
  { dx: -34, dy: -16 },
  { dx: 30, dy: 22 },
];

/* ==================================================================
   PLACEMENT
   ================================================================== */

/**
 * Evenly distributed points on a unit sphere, via the Fibonacci spiral.
 *
 * Uniform random points on a sphere clump — the eye reads the clumps as
 * structure that is not there. The golden-angle spiral has no clumps and no
 * visible seam, which is what makes a dotted sphere read as a surface rather
 * than as scattered confetti.
 */
export function fibonacciSphere(count: number): Vec3[] {
  const points: Vec3[] = new Array(count);
  const golden = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < count; i += 1) {
    // y walks the poles linearly; the radius of the circle at that height
    // follows, which is what keeps the density even rather than polar-heavy.
    const y = 1 - (i / (count - 1)) * 2;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * i;

    points[i] = { x: Math.cos(theta) * radius, y, z: Math.sin(theta) * radius };
  }

  return points;
}

/** Longitude/latitude to a point on the unit sphere. */
export function toVector(lon: number, lat: number): Vec3 {
  const cosLat = Math.cos(lat);
  return { x: Math.cos(lon) * cosLat, y: Math.sin(lat), z: Math.sin(lon) * cosLat };
}

/** The eight skill nodes as unit vectors, in `SKILL_NODES` order. */
export function nodeVectors(): Vec3[] {
  return NODE_POSITIONS.map(({ lon, lat }) => toVector(lon, lat));
}

/* ==================================================================
   TRANSFORM
   ================================================================== */

/**
 * Spin about the vertical axis, then tip forward, then divide by depth.
 *
 * One function rather than a matrix stack: there are exactly two rotations and
 * they never change order, so a 4x4 matrix and its multiply would be more code
 * to say the same thing and would run per point per frame.
 */
export function project(
  point: Vec3,
  angle: number,
  centreX: number,
  centreY: number,
  radius: number,
): Projected {
  const sinA = Math.sin(angle);
  const cosA = Math.cos(angle);

  const x1 = point.x * cosA + point.z * sinA;
  const z1 = -point.x * sinA + point.z * cosA;

  const sinT = Math.sin(TILT);
  const cosT = Math.cos(TILT);

  const y2 = point.y * cosT - z1 * sinT;
  const z2 = point.y * sinT + z1 * cosT;

  const scale = FOCAL / (FOCAL - z2);

  return {
    x: centreX + x1 * radius * scale,
    y: centreY + y2 * radius * scale,
    scale,
    depth: z2,
    normal: { x: x1, y: y2, z: z2 },
  };
}

/**
 * Direction the sphere is lit from, in the same space `project` returns.
 *
 * Screen `y` grows downward, so a negative `y` here is a light placed *above*
 * the sphere. Positive `z` puts it in front, toward the eye — behind the eye
 * would light only the hemisphere nobody can see.
 *
 * This is what makes the dot mesh read as a volume rather than a disc: without
 * a shading term the only cue is depth, and depth alone brightens the whole
 * near hemisphere evenly, which is exactly what a flat disc looks like.
 */
export const LIGHT: Vec3 = (() => {
  const raw = { x: -0.42, y: -0.38, z: 0.82 };
  const length = Math.hypot(raw.x, raw.y, raw.z);
  return { x: raw.x / length, y: raw.y / length, z: raw.z / length };
})();

/**
 * Lambert term for a surface normal, 0 (facing away) to 1 (facing the light).
 *
 * `normal` comes straight off `project`: a point on the unit sphere *is* its
 * own surface normal, so the rotated position doubles as the normal and no
 * separate normal transform is needed.
 */
export function lambert(normal: Vec3): number {
  return Math.max(0, normal.x * LIGHT.x + normal.y * LIGHT.y + normal.z * LIGHT.z);
}

/* ==================================================================
   ARCS
   ================================================================== */

/**
 * A point at `u` (0–1) along the flight path from `from` to `to`.
 *
 * Spherical interpolation, so the path follows the great circle between the two
 * nodes and stays on the surface the way a route on a globe does — a straight
 * line in 3D would cut through the sphere and disappear behind it.
 *
 * The path is then lifted off the surface by a sine bump, peaking at the
 * midpoint. Without the lift the arc is hidden by the very dots it travels
 * over; with it, the trace reads as an arc above the sphere.
 */
export function arcPoint(from: Vec3, to: Vec3, u: number, lift = 0.16): Vec3 {
  const dot = Math.min(1, Math.max(-1, from.x * to.x + from.y * to.y + from.z * to.z));
  const omega = Math.acos(dot);

  // Antipodal or identical endpoints have no unique great circle; fall back to
  // a straight blend rather than dividing by a vanishing sine.
  const sinOmega = Math.sin(omega);
  let x: number;
  let y: number;
  let z: number;

  if (sinOmega < 1e-4) {
    x = from.x + (to.x - from.x) * u;
    y = from.y + (to.y - from.y) * u;
    z = from.z + (to.z - from.z) * u;
  } else {
    const a = Math.sin((1 - u) * omega) / sinOmega;
    const b = Math.sin(u * omega) / sinOmega;
    x = from.x * a + to.x * b;
    y = from.y * a + to.y * b;
    z = from.z * a + to.z * b;
  }

  const length = Math.hypot(x, y, z) || 1;
  const height = 1 + Math.sin(Math.PI * u) * lift;

  return { x: (x / length) * height, y: (y / length) * height, z: (z / length) * height };
}

/**
 * Sphere radius for a given viewport, in CSS pixels.
 *
 * The brief asks for roughly 60% of viewport height, which is a radius of 0.3h.
 * That is held on desktop, but capped against width too — at a 21:9 aspect the
 * height-derived value would run the sphere off both sides.
 *
 * Narrow viewports get a smaller sphere because the copy stacks *over* it there
 * rather than sitting beside it, so the full 0.3h would put the wordmark on top
 * of the densest part of the mesh.
 */
export function sphereRadius(width: number, height: number): number {
  const heightFactor = width < 900 ? 0.24 : 0.3;
  return Math.min(height * heightFactor, width * 0.34);
}

/**
 * Where the sphere's centre sits.
 *
 * VERTICALLY CENTRED, and this is the part that was wrong. The centre used to
 * sit at 0.44h, which put the top of the sphere within about 50px of the fixed
 * 72px nav and clipped the whole upper half of the atmosphere glow off the top
 * of the canvas — the sphere read as cropped and top-heavy with a pool of empty
 * space beneath it.
 *
 * At 0.5h the silhouette spans 0.2h–0.8h with the glow's visible extent inside
 * the frame on both sides, so the space above and below is balanced. Nothing
 * competes for that room: the copy is bottom-*left* and the sphere is
 * right-of-centre, so on desktop they never share a column.
 *
 * Narrow viewports keep the centre a little high, because there the copy runs
 * the full width underneath and the sphere has to clear it.
 */
export function sphereCentre(width: number, height: number): { x: number; y: number } {
  return { x: width * (width < 900 ? 0.5 : 0.66), y: height * (width < 900 ? 0.4 : 0.5) };
}
