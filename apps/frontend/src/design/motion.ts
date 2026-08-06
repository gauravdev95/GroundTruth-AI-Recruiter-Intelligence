/**
 * Motion infrastructure — the whole product, landing page included.
 *
 * This module was `features/landing/lib/motion.ts`. It was promoted here
 * unchanged in behaviour when the authenticated surface adopted the same
 * design language; `features/landing/lib/motion.ts` is now a re-export shim
 * so the landing page's imports keep working and there is still exactly one
 * rAF loop and one observer registry for the entire application. Duplicating
 * it would have produced two loops, two registries, and two answers to
 * `prefers-reduced-motion`.
 *
 * Framer Motion is the only animation library. GSAP, ScrollTrigger and Lenis
 * were removed: two libraries contending for the same `transform` property is
 * a correctness problem before it is a bundle problem.
 *
 * FIVE RULES HOLD EVERYWHERE IN HERE
 *
 * 1. Only `transform` and `opacity` are ever animated. Two declared
 *    exceptions exist product-wide: SVG `pathLength` (the progress ring and
 *    the draw-on check) and `height` on disclosure panels, because neither
 *    has a transform-based equivalent that preserves document flow.
 * 2. `prefers-reduced-motion: reduce` is a real code path, subscribed rather
 *    than sampled once — every hook resolves to its final state when it is
 *    set, and reacts if the user changes it mid-session.
 * 3. There is exactly one `IntersectionObserver` per distinct set of observer
 *    options, and exactly one `requestAnimationFrame` loop, application-wide.
 * 4. Nothing survives unmount. Every subscription returns its own teardown.
 * 5. Every animation carries meaning. The taxonomy in `PURPOSE` below is the
 *    closed set of things motion is allowed to say in this product; an
 *    animation that does not map to one of them does not ship.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/* ==================================================================
   TOKENS — no animation anywhere in the product uses a literal
   ================================================================== */

/** Seconds. Framer Motion's unit, so no conversion happens at call sites. */
export const DURATION = {
  instant: 0.12,
  fast: 0.2,
  base: 0.32,
  slow: 0.56,
  cinematic: 0.9,
  /**
   * Count-up only, and longer than `cinematic` on purpose. A statistic is read
   * while it moves, so the digits have to stay legible for long enough to be
   * taken in — a 0.9s ramp to 1,300 is a blur with a number at the end of it.
   */
  count: 1.5,
} as const;

/**
 * Cubic-bezier control points. Typed as fixed-length tuples because Framer
 * Motion's `Easing` union accepts a 4-tuple, not `number[]`.
 */
type Bezier = [number, number, number, number];

export const EASE: Record<"entrance" | "standard" | "exit" | "overshoot", Bezier> = {
  /** Decelerating. Every reveal in the product uses this one. */
  entrance: [0.16, 1, 0.3, 1],
  standard: [0.22, 1, 0.36, 1],
  exit: [0.4, 0, 1, 1],
  /**
   * Slight overshoot past the target before settling. Reserved for moments
   * that celebrate a completed action — a step check, a strength jump — and
   * banned everywhere else. Overshoot on a routine transition reads as the
   * interface being unsure where it was going.
   */
  overshoot: [0.34, 1.56, 0.64, 1],
};

/** Pointer-driven motion only — magnetic pull, shared-element travel. */
export const SPRING = {
  type: "spring",
  stiffness: 200,
  damping: 24,
  mass: 0.6,
} as const;

/**
 * Softer, heavier spring for elements that carry weight across a layout —
 * the wizard's step indicator sliding between positions, a card reordering
 * itself. `SPRING` is too eager for anything that moves more than ~40px.
 */
export const SPRING_TRAVEL = {
  type: "spring",
  stiffness: 140,
  damping: 26,
  mass: 0.9,
} as const;

export const STAGGER = {
  siblings: 0.06,
  cards: 0.12,
  /** Seconds between beats of a multi-stage sequence. */
  pipelineStage: 0.4,
  /** The landing hero console's beat. See the landing page's own notes. */
  consoleBeat: 0.16,
  /**
   * The onboarding worker log's beat. Slower than `consoleBeat` because the
   * student is *reading* these lines rather than watching a demo scroll past
   * — each line is a claim about what is happening to their data, and a line
   * that appears faster than it can be read is decoration pretending to be
   * a status report.
   */
  workerLine: 0.28,
} as const;

/** Max travel for any reveal. Longer slide-ins read as templated. */
export const TRAVEL = 18;

/** The one viewport margin every scroll reveal shares. */
export const REVEAL_MARGIN = "-15% 0px -10% 0px";

/**
 * The closed set of things motion is permitted to communicate.
 *
 * Documentation, not runtime config — nothing imports this to make a
 * decision. It exists so that "every animation should have meaning" is
 * checkable in review rather than aspirational: a new animation must be
 * assignable to exactly one of these, and the reviewer's question is which.
 *
 * `orient`   — where did this come from, where did it go. Route transitions,
 *              wizard steps, modal origin. Answers "where am I".
 * `confirm`  — the system received your input. Button press, field valid,
 *              toggle flip. Answers "did that register".
 * `progress` — work is happening and here is how much is left. Upload bars,
 *              worker logs, skeleton shimmer. Answers "is it stuck".
 * `reveal`   — new content has arrived and is worth your attention. Card
 *              entrance, section stagger, detected-skill chips.
 * `celebrate`— something the student worked for is now true. Step complete,
 *              repository verified, interview finished. The only category
 *              permitted overshoot, and the only one permitted --glow-verified.
 * `warn`     — something needs correction before proceeding. Field shake,
 *              error slide. Never bounces; a playful error is condescending.
 */
export const PURPOSE = ["orient", "confirm", "progress", "reveal", "celebrate", "warn"] as const;

export type MotionPurpose = (typeof PURPOSE)[number];

/* ==================================================================
   MEDIA QUERIES — subscribed, not sampled
   ================================================================== */

function useMediaQuery(query: string): boolean {
  // Read synchronously during the first render so the initial paint is already
  // correct. Deciding this in an effect would flash the animated state at users
  // who asked for no animation.
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    const list = window.matchMedia(query);
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);

    setMatches(list.matches);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/**
 * The single source of truth for reduced motion. Every animated component in
 * the product consumes this hook; nothing writes its own media query.
 */
export function useReducedMotionSafe(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}

/** Scenes that need a different composition, not a smaller one, below 720px. */
export function useIsNarrow(): boolean {
  return useMediaQuery("(max-width: 720px)");
}

/** The tablet break. The wizard collapses its side rail here, not its steps. */
export function useIsTablet(): boolean {
  return useMediaQuery("(max-width: 1024px)");
}

/** True on touch-primary devices, where magnetism and ripples are noise. */
export function useIsTouch(): boolean {
  return useMediaQuery("(hover: none)");
}

/**
 * Imperative read, for the places that need the value outside React's render
 * cycle (the shared rAF loop, the magnetic pointer handler, the confetti
 * emitter). Components must use `useReducedMotionSafe` — this does not
 * subscribe.
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ==================================================================
   SHARED rAF LOOP — one clock for the whole application
   ================================================================== */

type FrameCallback = (now: number) => void;

const frameCallbacks = new Set<FrameCallback>();
let frameHandle = 0;

function runFrame(now: number) {
  frameHandle = 0;
  // Iterate a copy: a callback may unsubscribe itself on its final frame.
  for (const callback of [...frameCallbacks]) callback(now);
  scheduleFrame();
}

function scheduleFrame() {
  if (frameHandle) return;
  if (frameCallbacks.size === 0) return;
  if (typeof document !== "undefined" && document.hidden) return;
  frameHandle = requestAnimationFrame(runFrame);
}

if (typeof document !== "undefined") {
  // Ambient loops must not burn frames in a background tab. This matters more
  // in the app than it did on the landing page: a student can leave the
  // onboarding wizard open in a tab for an hour while its worker log polls.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (frameHandle) cancelAnimationFrame(frameHandle);
      frameHandle = 0;
    } else {
      scheduleFrame();
    }
  });
}

/**
 * Adds a callback to the application's single rAF loop. The loop starts on the
 * first subscription and stops entirely when the last one leaves, so an idle
 * screen schedules no frames at all.
 */
export function subscribeFrame(callback: FrameCallback): () => void {
  frameCallbacks.add(callback);
  scheduleFrame();

  return () => {
    frameCallbacks.delete(callback);
    if (frameCallbacks.size === 0 && frameHandle) {
      cancelAnimationFrame(frameHandle);
      frameHandle = 0;
    }
  };
}

/* ==================================================================
   SHARED INTERSECTION OBSERVER REGISTRY
   ================================================================== */

interface ObserveOptions {
  rootMargin?: string;
  threshold?: number;
}

type IntersectionCallback = (isIntersecting: boolean) => void;

const observers = new Map<string, IntersectionObserver>();
const elementCallbacks = new WeakMap<Element, Set<IntersectionCallback>>();

function getObserver(key: string, options: ObserveOptions): IntersectionObserver {
  const existing = observers.get(key);
  if (existing) return existing;

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const callbacks = elementCallbacks.get(entry.target);
        if (!callbacks) continue;
        for (const callback of [...callbacks]) callback(entry.isIntersecting);
      }
    },
    { rootMargin: options.rootMargin, threshold: options.threshold ?? 0 },
  );

  observers.set(key, observer);
  return observer;
}

/**
 * Registers interest in an element's visibility. Elements sharing the same
 * observer options share one `IntersectionObserver` instance, so a dashboard
 * with forty reveals allocates one observer rather than forty.
 */
export function observeIntersection(
  element: Element,
  callback: IntersectionCallback,
  options: ObserveOptions = {},
): () => void {
  const key = `${options.rootMargin ?? "0px"}|${options.threshold ?? 0}`;
  const observer = getObserver(key, options);

  let callbacks = elementCallbacks.get(element);
  if (!callbacks) {
    callbacks = new Set();
    elementCallbacks.set(element, callbacks);
  }
  callbacks.add(callback);
  observer.observe(element);

  return () => {
    const remaining = elementCallbacks.get(element);
    remaining?.delete(callback);
    if (!remaining || remaining.size === 0) {
      observer.unobserve(element);
      elementCallbacks.delete(element);
    }
  };
}

interface InViewOptions extends ObserveOptions {
  /** Stop observing after the first intersection. Default true. */
  once?: boolean;
}

/**
 * `[ref, inView]` on the shared observer.
 *
 * Reduced motion reports `true` on the first render: every scene's final state
 * is its reduced-motion state, so nothing waits for a scroll event that a user
 * who has asked for no motion may never generate.
 *
 * If `IntersectionObserver` is missing, `inView` is `true` from the start. No
 * content anywhere in this product may depend on an observer firing to become
 * visible.
 */
export function useInViewShared<T extends Element = HTMLDivElement>(options: InViewOptions = {}) {
  const { once = true, rootMargin = REVEAL_MARGIN, threshold } = options;
  const reduced = useReducedMotionSafe();
  const ref = useRef<T>(null);

  const [inView, setInView] = useState(() => {
    if (typeof window === "undefined") return true;
    if (typeof IntersectionObserver === "undefined") return true;
    return prefersReducedMotion();
  });

  useEffect(() => {
    if (reduced) {
      setInView(true);
      return;
    }

    const element = ref.current;
    if (!element) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }

    let stop: (() => void) | undefined;

    /*
     * Failsafe. One-shot reveals gate content, so an observer that never
     * reports at all — a browser quirk, a detached subtree — would strand that
     * content invisible forever.
     *
     * The signal is "the observer delivered a callback", not "the element is
     * visible": `IntersectionObserver` always makes an initial observation for
     * every element it is given, including a negative one. So the first
     * callback of any kind proves the observer works and cancels this timer,
     * and below-fold content is never force-revealed early.
     */
    let reported = false;
    const failsafe = window.setTimeout(() => {
      if (!reported) setInView(true);
    }, 1500);

    stop = observeIntersection(
      element,
      (isIntersecting) => {
        reported = true;
        window.clearTimeout(failsafe);
        setInView(isIntersecting);
        if (isIntersecting && once) {
          stop?.();
          stop = undefined;
        }
      },
      { rootMargin, threshold },
    );

    return () => {
      window.clearTimeout(failsafe);
      stop?.();
    };
  }, [once, reduced, rootMargin, threshold]);

  return [ref, inView] as const;
}

/**
 * True once the browser has gone idle, or after `timeout` ms at the latest.
 *
 * Used to keep an autoplaying scene from competing with first paint. In the
 * app this guards the dashboard's entrance stagger, which otherwise runs
 * inside the same window that decides LCP.
 */
export function useAfterIdle(timeout = 500): boolean {
  const [idle, setIdle] = useState(false);

  useEffect(() => {
    if (typeof requestIdleCallback !== "function") {
      const fallback = window.setTimeout(() => setIdle(true), timeout);
      return () => window.clearTimeout(fallback);
    }

    const handle = requestIdleCallback(() => setIdle(true), { timeout });
    return () => cancelIdleCallback(handle);
  }, [timeout]);

  return idle;
}

/* ==================================================================
   SEQUENCER — multi-beat scenes, on the shared clock
   ================================================================== */

interface SequenceOptions {
  /** Number of beats, including the resting final state. */
  steps: number;
  /** Seconds between beats. Defaults to the `pipelineStage` token. */
  interval?: number;
  /** The sequence only advances while this is true. */
  enabled?: boolean;
}

interface SequenceState {
  /** Current beat, 0-indexed. Equals `steps - 1` once the scene has settled. */
  step: number;
  /** True while beats are still advancing. */
  running: boolean;
  /** Restarts from beat 0. A no-op under reduced motion. */
  replay: () => void;
}

/**
 * Advances an integer beat counter on the shared rAF loop.
 *
 * Timing comes from frame timestamps rather than `setTimeout`, so a scene that
 * is paused (tab hidden, scrolled away) resumes from where it stopped instead
 * of jumping. Under reduced motion the counter starts at its final beat and
 * never moves — the scene renders assembled, which is the same state the
 * animation ends in.
 */
export function useSequence({
  steps,
  interval = STAGGER.pipelineStage,
  enabled = true,
}: SequenceOptions): SequenceState {
  const reduced = useReducedMotionSafe();
  const last = Math.max(0, steps - 1);

  const [step, setStep] = useState(() => (prefersReducedMotion() ? last : 0));
  const [runToken, setRunToken] = useState(0);

  const running = !reduced && step < last;

  useEffect(() => {
    if (reduced) {
      setStep(last);
      return;
    }
    if (!enabled) return;
    if (step >= last) return;

    let startedAt = 0;
    let stepAtStart = step;

    const stop = subscribeFrame((now) => {
      if (!startedAt) {
        startedAt = now;
        return;
      }

      const elapsed = (now - startedAt) / 1000;
      const target = Math.min(last, stepAtStart + Math.floor(elapsed / interval));

      setStep((current) => {
        if (target <= current) return current;
        // Re-anchor so the next beat is measured from this one, not from mount.
        startedAt = now;
        stepAtStart = target;
        return target;
      });
    });

    return stop;
    // `step` is intentionally excluded: it would tear down and rebuild the
    // subscription on every beat. `runToken` is the deliberate restart signal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, interval, last, reduced, runToken]);

  const replay = useCallback(() => {
    if (prefersReducedMotion()) return;
    setStep(0);
    setRunToken((token) => token + 1);
  }, []);

  return { step, running, replay };
}

/* ==================================================================
   COUNT-UP — for every number that earns its way upward
   ================================================================== */

/**
 * Eases a displayed number from its previous value to `value`.
 *
 * Exists because profile strength, evidence score and interview score all
 * change as a *result* of something the student did, and snapping the digits
 * discards the causal link between the action and the reward. Counting up is
 * `celebrate`, not decoration.
 *
 * Three behaviours worth knowing:
 *
 * * The first observed value is adopted instantly, never counted up from
 *   zero. A returning student's dashboard showing 68 must not animate
 *   0 → 68 on every mount — that would re-celebrate work they finished last
 *   week, and it would make the number untrustworthy as a status readout.
 * * Downward changes are also animated. A strength that fell because a claim
 *   was rejected is information the student needs to *see* move, and snapping
 *   it would hide the one case where the direction matters most.
 * * Under reduced motion the value is always adopted instantly.
 */
// `duration: number` and not the inferred literal: `DURATION.slow` is `0.56`
// under `as const`, so an inferred default would type this parameter as the
// literal 0.56 and reject every other token in the same object.
export function useCountUp(value: number, duration: number = DURATION.slow): number {
  const reduced = useReducedMotionSafe();
  const [display, setDisplay] = useState(value);
  const previous = useRef(value);
  // `null` until the first real value has been adopted, which is what
  // distinguishes "mounted with 68" from "changed to 68".
  const hasAdopted = useRef(false);

  useEffect(() => {
    if (!hasAdopted.current) {
      hasAdopted.current = true;
      previous.current = value;
      setDisplay(value);
      return;
    }

    if (reduced || value === previous.current) {
      previous.current = value;
      setDisplay(value);
      return;
    }

    const from = previous.current;
    const delta = value - from;
    previous.current = value;

    let startedAt = 0;

    const stop = subscribeFrame((now) => {
      if (!startedAt) startedAt = now;
      const elapsed = (now - startedAt) / 1000;
      const t = Math.min(1, elapsed / duration);
      // Cubic ease-out. Matches EASE.entrance closely enough that a counter
      // and the card revealing it read as one gesture, without importing a
      // bezier solver to animate a single scalar.
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + delta * eased);
      if (t >= 1) stop();
    });

    return stop;
  }, [value, duration, reduced]);

  return display;
}

/* ==================================================================
   MAGNETIC POINTER PULL
   ================================================================== */

/**
 * Magnetic pull toward the cursor, capped at `max` px.
 *
 * Deliberately library-free: this runs on primary CTAs, and the release is a
 * CSS transition so letting go costs no frames. Pointer reads are throttled
 * to one per frame on the shared loop.
 */
export function useMagnetic<T extends HTMLElement = HTMLAnchorElement>(max = 6) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (prefersReducedMotion()) return;
    if (window.matchMedia("(hover: none)").matches) return;

    let pending: PointerEvent | null = null;
    let unsubscribe: (() => void) | undefined;

    const apply = () => {
      const event = pending;
      pending = null;
      unsubscribe?.();
      unsubscribe = undefined;
      if (!event) return;

      const box = element.getBoundingClientRect();
      const dx = event.clientX - (box.left + box.width / 2);
      const dy = event.clientY - (box.top + box.height / 2);
      const distance = Math.hypot(dx, dy) || 1;
      const pull = Math.min(distance, max) / distance;

      element.style.transition = "none";
      element.style.transform = `translate3d(${dx * pull}px, ${dy * pull}px, 0)`;
    };

    const onEnter = () => {
      // `will-change` is applied on interaction and removed on release, never
      // left on statically.
      element.style.willChange = "transform";
    };

    const onMove = (event: PointerEvent) => {
      pending = event;
      if (!unsubscribe) unsubscribe = subscribeFrame(apply);
    };

    const onLeave = () => {
      pending = null;
      unsubscribe?.();
      unsubscribe = undefined;
      element.style.transition = "transform 0.34s cubic-bezier(0.34, 1.56, 0.64, 1)";
      element.style.transform = "translate3d(0, 0, 0)";
      element.style.willChange = "";
    };

    element.addEventListener("pointerenter", onEnter);
    element.addEventListener("pointermove", onMove);
    element.addEventListener("pointerleave", onLeave);

    return () => {
      element.removeEventListener("pointerenter", onEnter);
      element.removeEventListener("pointermove", onMove);
      element.removeEventListener("pointerleave", onLeave);
      unsubscribe?.();
      element.style.willChange = "";
    };
  }, [max]);

  return ref;
}
