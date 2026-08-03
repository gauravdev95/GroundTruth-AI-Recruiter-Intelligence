import type { CSSProperties, ReactNode } from "react";
import { motion } from "framer-motion";

import { DURATION, EASE, STAGGER, TRAVEL, useInViewShared, useReducedMotionSafe } from "../lib/motion";

interface StaggerProps {
  children: ReactNode;
  /** Seconds between siblings. Use a token: `STAGGER.siblings` or `.cards`. */
  gap?: number;
  className?: string;
  style?: CSSProperties;
  /** Renders as a `<ul>` when its children are `<StaggerItem as="li">`. */
  as?: "div" | "ul" | "ol";
}

/**
 * Reveals its children in sequence when the container scrolls into view.
 *
 * One observer for the whole list rather than one per row: the container is
 * observed, and the beat is propagated to children through Framer Motion's
 * variant tree, so a five-row section costs one IntersectionObserver entry.
 *
 * Children must be `<StaggerItem>` (or any `motion` element declaring the same
 * `out`/`in` variant names) for propagation to reach them.
 */
export function Stagger({
  children,
  gap = STAGGER.siblings,
  className,
  style,
  as = "div",
}: StaggerProps) {
  const reduced = useReducedMotionSafe();
  const [ref, inView] = useInViewShared<HTMLDivElement>();

  /*
   * `motion[as]` is a union of three components, and TypeScript intersects their
   * `ref` types into something no single element satisfies. The tag string is
   * what decides the rendered element, so narrowing the type to one member is
   * accurate at runtime and keeps the ref assignable.
   */
  const Element = motion[as] as typeof motion.div;

  return (
    <Element
      ref={ref}
      className={className}
      style={style}
      variants={{
        out: {},
        in: { transition: { staggerChildren: reduced ? 0 : gap } },
      }}
      initial={reduced ? "in" : "out"}
      animate={inView ? "in" : "out"}
    >
      {children}
    </Element>
  );
}

interface StaggerItemProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  as?: "div" | "li";
}

/** One beat of a `<Stagger>`. Inherits its timing from the parent's variants. */
export function StaggerItem({ children, className, style, as = "div" }: StaggerItemProps) {
  const reduced = useReducedMotionSafe();
  const Element = motion[as] as typeof motion.div;

  return (
    <Element
      className={className}
      style={style}
      variants={{
        out: { opacity: 0, y: TRAVEL },
        in: { opacity: 1, y: 0 },
      }}
      transition={{ duration: reduced ? 0 : DURATION.base, ease: EASE.entrance }}
    >
      {children}
    </Element>
  );
}
