/**
 * Motion primitives — the vocabulary every animated screen is built from.
 *
 * Six components, each mapping to exactly one entry in `motion.ts`'s
 * `PURPOSE` taxonomy. A screen that needs motion composes these; it does not
 * write its own `<motion.div>` with literal durations, because that is how a
 * design system becomes forty slightly-different fade-ins.
 *
 *   Reveal       → reveal      content has arrived
 *   Stagger      → reveal      several things arrived, in order
 *   Celebrate    → celebrate   something the student worked for is now true
 *   ProgressRing → progress    how much is left, as a shape
 *   Shake        → warn        this needs correction
 *   Transition   → orient      you moved from one place to another
 *
 * Every one of them resolves to its final state under reduced motion. That is
 * not a fallback path bolted on afterwards — it is why each of these takes
 * its "done" state as a prop rather than deriving it from an animation
 * completing. An animation that never runs must still leave the UI correct.
 */

import { AnimatePresence, motion, type Variants } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";

import {
  DURATION,
  EASE,
  SPRING_TRAVEL,
  STAGGER,
  TRAVEL,
  useInViewShared,
  useReducedMotionSafe,
} from "./motion";

/* ==================================================================
   REVEAL — content has arrived
   ================================================================== */

interface RevealProps {
  children: ReactNode;
  /** Seconds. Use `STAGGER.*` tokens, never a literal. */
  delay?: number;
  /**
   * Reveal on scroll into view (default) or immediately on mount. Mount is
   * correct for anything above the fold — waiting for an intersection that
   * already happened costs a frame of blankness.
   */
  trigger?: "view" | "mount";
  className?: string;
  as?: "div" | "section" | "li" | "article";
}

/**
 * The one entrance animation in the product: 18px up, fading in, decelerating.
 *
 * `TRAVEL` is capped at 18px deliberately — longer slide-ins read as
 * templated, and on a dashboard where six cards reveal at once, longer
 * distances turn a composed entrance into a scramble.
 */
export function Reveal({
  children,
  delay = 0,
  trigger = "view",
  className,
  as = "div",
}: RevealProps) {
  const reduced = useReducedMotionSafe();
  const [ref, inView] = useInViewShared<HTMLDivElement>();

  // Narrowed to `motion.div`'s type on purpose. `motion[as]` is a union of
  // four component types, and TypeScript intersects their `ref` props into
  // `RefObject<HTMLDivElement> & RefObject<HTMLLIElement> & …` — a type no
  // real ref can satisfy. The rendered tag is still whatever `as` names;
  // only the prop typing is collapsed, and every prop passed below is common
  // to all four.
  const Component = motion[as] as typeof motion.div;

  const show = reduced || trigger === "mount" || inView;

  return (
    <Component
      ref={trigger === "view" ? ref : undefined}
      className={className}
      initial={reduced ? false : { opacity: 0, y: TRAVEL }}
      animate={show ? { opacity: 1, y: 0 } : { opacity: 0, y: TRAVEL }}
      transition={{ duration: DURATION.base, ease: EASE.entrance, delay: reduced ? 0 : delay }}
    >
      {children}
    </Component>
  );
}

/* ==================================================================
   STAGGER — several things arrived, in order
   ================================================================== */

const staggerParent: Variants = {
  hidden: {},
  shown: (interval: number) => ({
    transition: { staggerChildren: interval },
  }),
};

const staggerChild: Variants = {
  hidden: { opacity: 0, y: TRAVEL },
  shown: { opacity: 1, y: 0, transition: { duration: DURATION.base, ease: EASE.entrance } },
};

interface StaggerProps {
  children: ReactNode;
  /** Seconds between children. Defaults to the `siblings` token. */
  interval?: number;
  className?: string;
}

/**
 * Reveals children in sequence. Wrap each child in `<Stagger.Item>`.
 *
 * Order carries meaning here: the dashboard staggers top-left to bottom-right
 * so the eye is led along the reading path rather than pulled around the
 * screen. A stagger that fires in DOM order which is not visual order is
 * worse than no stagger at all.
 */
export function Stagger({ children, interval = STAGGER.siblings, className }: StaggerProps) {
  const reduced = useReducedMotionSafe();
  const [ref, inView] = useInViewShared<HTMLDivElement>();

  return (
    <motion.div
      ref={ref}
      className={className}
      variants={staggerParent}
      custom={reduced ? 0 : interval}
      initial={reduced ? "shown" : "hidden"}
      animate={reduced || inView ? "shown" : "hidden"}
    >
      {children}
    </motion.div>
  );
}

Stagger.Item = function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div className={className} variants={staggerChild}>
      {children}
    </motion.div>
  );
};

/* ==================================================================
   CELEBRATE — something the student worked for is now true
   ================================================================== */

interface CelebrateProps {
  children: ReactNode;
  /**
   * Flips false → true at the moment of achievement. Held true afterwards:
   * the burst plays once per transition, not once per render, so a refetch
   * that re-confirms the same success does not re-fire it.
   */
  active: boolean;
  className?: string;
}

/**
 * A single scale-overshoot pulse plus a radial bloom in `--glow-verified`.
 *
 * This is the ONE place green is permitted as light rather than as status
 * (see `tokens.css` rule 1). The exemption is narrow and deliberate: a burst
 * is unattached to any claim, lasts under a second, and never appears beside
 * an unproven one — so it cannot be mistaken for a verification badge.
 *
 * No confetti. Confetti is celebration applied uniformly regardless of what
 * was achieved, and this product's whole thesis is that achievements are
 * specific and earned. The pulse is sized to the thing that succeeded.
 */
export function Celebrate({ children, active, className }: CelebrateProps) {
  const reduced = useReducedMotionSafe();
  // Latches so the burst plays on the transition into `active`, not on every
  // render while `active` stays true.
  const [burst, setBurst] = useState(false);
  const wasActive = useRef(active);

  useEffect(() => {
    if (active && !wasActive.current) {
      setBurst(true);
      const timer = window.setTimeout(() => setBurst(false), DURATION.cinematic * 1000);
      wasActive.current = active;
      return () => window.clearTimeout(timer);
    }
    wasActive.current = active;
  }, [active]);

  return (
    <div className={`relative ${className ?? ""}`}>
      <AnimatePresence>
        {burst && !reduced ? (
          <motion.span
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-1/2 -z-10 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full"
            style={{
              background:
                "radial-gradient(circle, rgb(var(--glow-verified) / 0.28) 0%, transparent 70%)",
            }}
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1.6, opacity: [0, 1, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.cinematic, ease: EASE.entrance }}
          />
        ) : null}
      </AnimatePresence>

      <motion.div
        animate={burst && !reduced ? { scale: [1, 1.06, 1] } : { scale: 1 }}
        transition={{ duration: DURATION.slow, ease: EASE.overshoot }}
      >
        {children}
      </motion.div>
    </div>
  );
}

/* ==================================================================
   PROGRESS RING — how much is left, as a shape
   ================================================================== */

interface ProgressRingProps {
  /** 0-100. */
  value: number;
  size?: number;
  strokeWidth?: number;
  /** Rendered inside the ring. Usually a `useCountUp` figure. */
  children?: ReactNode;
  className?: string;
}

/**
 * The profile-strength ring.
 *
 * Animates SVG `strokeDashoffset` — one of the two declared exceptions to the
 * transform-and-opacity rule (`motion.ts`), because there is no transform
 * that sweeps an arc without also scaling its stroke.
 *
 * The track is `--rule` and the sweep is a violet→blue gradient. Deliberately
 * NOT green: profile strength measures what is *filled*, not what is
 * verified (`completeness.py` is explicit that the two are different numbers),
 * and a green ring would claim verification the student has not earned. This
 * is the most likely place in the whole product for that mistake to be made,
 * which is why it is called out here rather than only in the token file.
 */
export function ProgressRing({
  value,
  size = 120,
  strokeWidth = 8,
  children,
  className,
}: ProgressRingProps) {
  const reduced = useReducedMotionSafe();
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className ?? ""}`}
      role="img"
      aria-label={`Profile strength ${Math.round(clamped)} percent`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id="gt-ring" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--violet)" />
            <stop offset="100%" stopColor="var(--blue)" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--rule)"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#gt-ring)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={reduced ? false : { strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: reduced ? 0 : DURATION.cinematic, ease: EASE.entrance }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">{children}</div>
    </div>
  );
}

/* ==================================================================
   SHAKE — this needs correction
   ================================================================== */

/**
 * A short lateral shake on validation failure.
 *
 * Two amplitude notes, both deliberate: the travel is 4px and the duration is
 * `fast`. Anything larger or slower becomes playful, and a playful error is
 * condescending to someone who has just been told they did something wrong.
 * It also never bounces — `EASE.overshoot` is reserved for `celebrate`.
 */
export function Shake({
  children,
  active,
  className,
}: {
  children: ReactNode;
  active: boolean;
  className?: string;
}) {
  const reduced = useReducedMotionSafe();

  return (
    <motion.div
      className={className}
      animate={active && !reduced ? { x: [0, -4, 4, -3, 0] } : { x: 0 }}
      transition={{ duration: DURATION.fast, ease: EASE.standard }}
    >
      {children}
    </motion.div>
  );
}

/* ==================================================================
   TRANSITION — you moved from one place to another
   ================================================================== */

interface TransitionProps {
  children: ReactNode;
  /** Changes on navigation. Usually the route path or the wizard step index. */
  routeKey: string | number;
  /**
   * `forward` slides in from the right, `back` from the left. The wizard
   * passes direction so a student stepping backward sees the reverse of what
   * brought them here — motion that contradicts the navigation is worse than
   * none, because it silently tells them they went the wrong way.
   */
  direction?: "forward" | "back";
  className?: string;
}

export function Transition({
  children,
  routeKey,
  direction = "forward",
  className,
}: TransitionProps) {
  const reduced = useReducedMotionSafe();
  const sign = direction === "forward" ? 1 : -1;

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={routeKey}
        className={className}
        initial={reduced ? false : { opacity: 0, x: sign * 24 }}
        animate={{ opacity: 1, x: 0 }}
        exit={reduced ? undefined : { opacity: 0, x: sign * -24 }}
        transition={reduced ? { duration: 0 } : SPRING_TRAVEL}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
