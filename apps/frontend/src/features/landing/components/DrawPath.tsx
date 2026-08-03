import { motion } from "framer-motion";

import { DURATION, EASE, useInViewShared, useReducedMotionSafe } from "../lib/motion";

interface DrawPathProps {
  /** SVG path data. */
  d: string;
  /**
   * Controlled draw state. Omit to let the path draw itself when it scrolls
   * into view; pass a boolean to drive it from a parent sequence instead.
   */
  draw?: boolean;
  /** Seconds. Defaults to the `slow` token. */
  duration?: number;
  /** Seconds. */
  delay?: number;
  strokeWidth?: number;
  strokeLinecap?: "butt" | "round" | "square";
  className?: string;
}

/**
 * A stroke that draws itself.
 *
 * `pathLength` is the single property on this page animated outside
 * `transform`/`opacity`. It is the correct exception: Framer Motion implements
 * it as `stroke-dasharray` + `stroke-dashoffset`, which repaints one stroke and
 * touches neither layout nor the compositor tree — and a self-drawing
 * checkmark is a mechanism the design brief asks for by name.
 *
 * Colour comes from `currentColor`, so a verified checkmark inherits the
 * semantic green from whatever surface it lands on, dark band or light.
 */
export function DrawPath({
  d,
  draw,
  duration = DURATION.slow,
  delay = 0,
  strokeWidth = 2.2,
  strokeLinecap = "square",
  className,
}: DrawPathProps) {
  const reduced = useReducedMotionSafe();
  const [ref, inView] = useInViewShared<SVGPathElement>();

  // Uncontrolled: the path is its own trigger. Controlled: the parent decides.
  const shouldDraw = draw ?? inView;

  return (
    <motion.path
      ref={ref}
      className={className}
      d={d}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap={strokeLinecap}
      initial={{ pathLength: reduced ? 1 : 0 }}
      animate={{ pathLength: shouldDraw ? 1 : 0 }}
      transition={{
        duration: reduced ? 0 : duration,
        ease: EASE.entrance,
        delay: reduced ? 0 : delay,
      }}
    />
  );
}
