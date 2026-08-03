import type { CSSProperties, ReactNode } from "react";
import { motion } from "framer-motion";

import { DURATION, EASE, TRAVEL, useInViewShared, useReducedMotionSafe } from "../lib/motion";

interface RevealProps {
  children: ReactNode;
  /** Milliseconds, to match the 60ms sibling rhythm used across the page. */
  delay?: number;
  className?: string;
  style?: CSSProperties;
}

/**
 * Fades and lifts its content into place the first time it scrolls into view.
 *
 * The hidden state is an inline style written by Framer Motion, never a
 * stylesheet rule. That distinction is the whole point: the old
 * `.rv { opacity: 0 }` rule meant every below-fold paragraph on the page was
 * invisible until an IntersectionObserver said otherwise, so copy depended on
 * JS to be readable. Now the resting state in CSS is "visible", and only a
 * running animation can hide anything.
 *
 * Under reduced motion this renders its final state on the first paint — no
 * transform, no observer, no wait.
 */
export function Reveal({ children, delay = 0, className, style }: RevealProps) {
  const reduced = useReducedMotionSafe();
  const [ref, inView] = useInViewShared<HTMLDivElement>();

  return (
    <motion.div
      ref={ref}
      className={className}
      style={style}
      variants={{
        out: { opacity: 0, y: TRAVEL },
        in: { opacity: 1, y: 0 },
      }}
      initial={reduced ? "in" : "out"}
      animate={inView ? "in" : "out"}
      transition={{
        duration: reduced ? 0 : DURATION.base,
        ease: EASE.entrance,
        delay: reduced ? 0 : delay / 1000,
      }}
    >
      {children}
    </motion.div>
  );
}
