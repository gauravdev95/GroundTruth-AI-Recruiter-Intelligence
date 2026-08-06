import { useEffect, useRef } from "react";

import { prefersReducedMotion, subscribeFrame } from "@/design/motion";

/* ==================================================================
   TUNING
   ================================================================== */

/**
 * The three drifting light sources.
 *
 * Each travels a Lissajous path — two sines at incommensurable rates — so the
 * composition never visibly repeats and no two blobs fall into a shared
 * rhythm. `radius` is a fraction of the smaller viewport axis, so the scene
 * has the same proportions on a phone as on a 27" display rather than three
 * small dots in a corner.
 *
 * Colours are the landing page's own: electric blue is the product accent, and
 * the violet is `gt-wash-to`, already used for the one decorative gradient the
 * landing page permits. Deliberately NOT `gt-ember` — that orange is
 * hero-scoped on the landing page, where it means "a verification event just
 * landed on the constellation". Nothing is verified on a sign-in form, and
 * spending a meaningful colour on decoration is how it stops meaning anything.
 */
const BLOBS = [
  { color: "37, 99, 235", radius: 0.72, x: [0.22, 0.14], y: [0.3, 0.1], rate: [0.037, 0.029] },
  { color: "124, 58, 237", radius: 0.58, x: [0.78, 0.12], y: [0.68, 0.13], rate: [0.023, 0.041] },
  { color: "30, 64, 255", radius: 0.46, x: [0.55, 0.18], y: [0.18, 0.09], rate: [0.047, 0.019] },
] as const;

/** Particles per megapixel, so density reads the same at every viewport size. */
const PARTICLE_DENSITY = 62;
const MAX_PARTICLES = 130;

/** Alpha buckets for the particle field — one `fill()` per bucket, matching
 *  the landing constellation's approach to the same problem. */
const PARTICLE_BUCKETS = 5;

interface Particle {
  x: number;
  y: number;
  size: number;
  /** Fraction of viewport height travelled per second. Always upward. */
  speed: number;
  /** Phase offset so no two particles peak together. */
  phase: number;
  /** Radians per second for this particle's own twinkle. */
  twinkle: number;
}

/**
 * The animated backdrop behind the sign-in and sign-up forms.
 *
 * WHAT IT IS. Three large, slowly drifting radial glows composited additively
 * over the landing hero's vertical ramp, plus a sparse field of upward-drifting
 * particles. It is decoration and nothing else — `aria-hidden`, non-interactive,
 * and no information is encoded in it.
 *
 * WHY NOT REUSE THE LANDING HERO'S `SkillConstellation`. It would have been
 * the obvious "same hero" answer, and it is the wrong one twice over. It draws
 * 2,500 sphere points and 1,400 stars every frame, which is a lot of budget to
 * spend behind a form whose job is to be typed into; and it carries meaning —
 * labelled skill nodes with orange arcs firing between them stand for
 * verification events, which is a claim a login page has no business making.
 * This scene says "the same product" through palette and motion without
 * borrowing a statement it cannot back.
 *
 * WHAT MAKES IT CHEAP
 *
 * * Each blob is rasterised **once** into an offscreen sprite on resize and
 *   then `drawImage`d at a moving offset. `createRadialGradient` is the most
 *   expensive call this API offers and it never runs inside the frame loop.
 * * Particles are bucketed by alpha and drawn with one `fill()` per bucket.
 * * It runs on the application's single shared rAF loop (`design/motion.ts`),
 *   which already stops itself in a background tab. Nothing here schedules its
 *   own frames.
 *
 * REDUCED MOTION IS HONOURED. Unlike the landing hero — which overrides it for
 * its centrepiece by explicit request — this scene is pure decoration on a
 * screen someone is trying to complete a task on. Under `prefers-reduced-motion`
 * it paints exactly one frame and never subscribes to the loop at all.
 */
export function AuthAurora() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let particles: Particle[] = [];
    let sprites: HTMLCanvasElement[] = [];

    let sceneTime = 0;
    let lastFrame = 0;

    /* Reused between frames so the draw loop allocates nothing. */
    const buckets: number[][] = Array.from({ length: PARTICLE_BUCKETS }, () => []);

    /* ---- sizing ----------------------------------------------------- */

    /**
     * One offscreen canvas per blob, holding its radial falloff at full size.
     *
     * Drawn at device pixels but sampled back at CSS pixels, so the sprite
     * stays soft rather than banded on a high-DPR screen. The falloff is
     * quartic-ish (four stops rather than a linear ramp) because a linear
     * radial gradient reads as a hard-edged disc at this scale.
     */
    function buildSprites() {
      const base = Math.min(width, height);

      sprites = BLOBS.map((blob) => {
        const radius = Math.max(1, base * blob.radius);
        const size = Math.ceil(radius * 2);

        const sprite = document.createElement("canvas");
        sprite.width = size;
        sprite.height = size;

        const spriteCtx = sprite.getContext("2d");
        if (!spriteCtx) return sprite;

        const gradient = spriteCtx.createRadialGradient(
          radius,
          radius,
          0,
          radius,
          radius,
          radius,
        );
        gradient.addColorStop(0, `rgba(${blob.color}, 0.32)`);
        gradient.addColorStop(0.28, `rgba(${blob.color}, 0.18)`);
        gradient.addColorStop(0.55, `rgba(${blob.color}, 0.07)`);
        gradient.addColorStop(0.8, `rgba(${blob.color}, 0.02)`);
        gradient.addColorStop(1, `rgba(${blob.color}, 0)`);

        spriteCtx.fillStyle = gradient;
        spriteCtx.fillRect(0, 0, size, size);
        return sprite;
      });
    }

    function buildParticles() {
      const count = Math.min(
        MAX_PARTICLES,
        Math.round((width * height) / 1_000_000 * PARTICLE_DENSITY),
      );

      particles = new Array(count);
      for (let i = 0; i < count; i += 1) {
        particles[i] = {
          x: Math.random() * width,
          y: Math.random() * height,
          size: Math.random() < 0.82 ? 1 : 1.8,
          // 1.2%–4% of viewport height per second. Slow enough to read as
          // ambient rather than as weather.
          speed: 0.012 + Math.random() * 0.028,
          phase: Math.random() * Math.PI * 2,
          twinkle: 0.3 + Math.random() * 0.7,
        };
      }
    }

    function resize() {
      const rect = canvas!.getBoundingClientRect();
      // Capped at 2, as elsewhere in this product: a 3x phone screen triples
      // fill cost for a difference nobody can see on 1px rectangles.
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      width = rect.width;
      height = rect.height;

      canvas!.width = Math.max(1, Math.floor(width * dpr));
      canvas!.height = Math.max(1, Math.floor(height * dpr));
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      buildSprites();
      buildParticles();
    }

    /* ---- drawing ---------------------------------------------------- */

    function drawBlobs(time: number) {
      // `lighter` adds rather than covers, so where two blobs overlap the
      // light accumulates instead of the nearer one winning. That overlap is
      // the whole effect — without it these are three flat discs.
      ctx!.globalCompositeOperation = "lighter";

      for (let i = 0; i < BLOBS.length; i += 1) {
        const blob = BLOBS[i];
        const sprite = sprites[i];
        if (!sprite) continue;

        const cx = (blob.x[0] + Math.sin(time * blob.rate[0] * Math.PI * 2) * blob.x[1]) * width;
        const cy = (blob.y[0] + Math.cos(time * blob.rate[1] * Math.PI * 2) * blob.y[1]) * height;
        const half = sprite.width / 2;

        ctx!.drawImage(sprite, cx - half, cy - half, sprite.width, sprite.height);
      }

      ctx!.globalCompositeOperation = "source-over";
    }

    function drawParticles(time: number, delta: number) {
      for (const bucket of buckets) bucket.length = 0;

      for (const particle of particles) {
        particle.y -= particle.speed * height * delta;
        // Wrap to the bottom with a fresh horizontal position, so the field
        // never settles into visible vertical lanes.
        if (particle.y < -4) {
          particle.y = height + 4;
          particle.x = Math.random() * width;
        }

        const wave = 0.5 + 0.5 * Math.sin(time * particle.twinkle + particle.phase);
        const alpha = 0.12 + wave * 0.34;
        const index = Math.min(
          PARTICLE_BUCKETS - 1,
          Math.max(0, Math.floor(((alpha - 0.12) / 0.34) * PARTICLE_BUCKETS)),
        );
        buckets[index].push(particle.x, particle.y, particle.size);
      }

      ctx!.fillStyle = "#FFFFFF";
      for (let b = 0; b < PARTICLE_BUCKETS; b += 1) {
        const bucket = buckets[b];
        if (bucket.length === 0) continue;

        ctx!.globalAlpha = 0.12 + ((b + 0.5) / PARTICLE_BUCKETS) * 0.34;
        ctx!.beginPath();
        for (let i = 0; i < bucket.length; i += 3) {
          ctx!.rect(bucket[i], bucket[i + 1], bucket[i + 2], bucket[i + 2]);
        }
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;
    }

    function draw(time: number, delta: number) {
      ctx!.clearRect(0, 0, width, height);
      drawBlobs(time);
      drawParticles(time, delta);
    }

    /* ---- wiring ----------------------------------------------------- */

    resize();

    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => resize()) : null;
    observer?.observe(canvas);

    if (prefersReducedMotion()) {
      // One frame, at a scene time chosen so the blobs sit apart rather than
      // stacked at their t=0 origins, and then nothing. No subscription means
      // no frames are ever scheduled on this route.
      draw(6, 0);
      return () => observer?.disconnect();
    }

    const unsubscribe = subscribeFrame((now) => {
      const seconds = now / 1000;
      if (!lastFrame) lastFrame = seconds;
      // Clamped: a tab restored after a minute must not advance the scene by a
      // minute in one step, which would teleport every blob and rain the whole
      // particle field off the top edge at once.
      const delta = Math.min(0.05, seconds - lastFrame);
      lastFrame = seconds;
      sceneTime += delta;

      draw(sceneTime, delta);
    });

    return () => {
      unsubscribe();
      observer?.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className="h-full w-full" />;
}
