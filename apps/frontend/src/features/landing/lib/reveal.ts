import {
  DURATION,
  EASE,
  STAGGER,
  TRAVEL,
  useInViewShared,
  useReducedMotionSafe,
} from "@/design/motion";

/**
 * The page's one entrance: fade up, once, on scroll into view.
 *
 * WHY NOT `whileInView`. Framer Motion's `whileInView` allocates its own
 * `IntersectionObserver` per element. This page has upwards of sixty revealed
 * elements, and the product's motion system exists specifically so that there
 * is one observer registry for the whole application — see the rules at the top
 * of `design/motion.ts`. `useInViewShared` reuses one observer across every
 * element that shares these options, which is all of them.
 *
 * `useInViewShared` also resolves to `true` immediately under reduced motion and
 * when `IntersectionObserver` is unavailable, so nothing on this page can be
 * left permanently invisible by a scroll event that never arrives.
 */
export function useReveal<T extends Element = HTMLDivElement>(delay = 0) {
  const reduced = useReducedMotionSafe();
  const [ref, inView] = useInViewShared<T>();

  if (reduced) {
    return { ref, initial: false as const, animate: { opacity: 1, y: 0 } };
  }

  return {
    ref,
    initial: { opacity: 0, y: TRAVEL },
    animate: inView ? { opacity: 1, y: 0 } : { opacity: 0, y: TRAVEL },
    transition: { duration: DURATION.slow, ease: EASE.standard, delay },
  };
}

/** Index-derived delay, so a row of cards arrives left to right. */
export function stagger(index: number, step: number = STAGGER.cards): number {
  return index * step;
}
