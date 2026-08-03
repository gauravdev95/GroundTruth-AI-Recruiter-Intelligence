import { useLayoutEffect, useRef } from "react";

import { DURATION, subscribeFrame, useInViewShared, useReducedMotionSafe } from "../lib/motion";

interface CounterProps {
  /** The real value. Rendered as text on the first paint. */
  to: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  /** Seconds. Defaults to the `cinematic` token. */
  duration?: number;
  className?: string;
}

/**
 * The `entrance` token's shape as a plain function for the frame loop. A full
 * cubic-bezier solver is overkill for a monotonic count: ease-out quint is the
 * same decelerating curve to within a pixel of readout.
 */
function easeEntrance(t: number): number {
  return 1 - Math.pow(1 - t, 5);
}

/**
 * Counts up to a metric when it scrolls into view.
 *
 * Two decisions worth stating. First, the value is written with
 * `ref.textContent` from the shared rAF loop rather than through state: a
 * counter driven by `setState` re-renders its subtree sixty times a second for
 * no visual gain. Second, the final value is what React actually renders, and
 * the count-down to zero happens in a layout effect before paint — so if
 * scripting stops at any point the number on screen is the true one, never a
 * frozen `0`.
 *
 * Formatting uses `tabular-nums` via the stylesheet so the surrounding layout
 * cannot shift as digits change.
 */
export function Counter({
  to,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = DURATION.cinematic,
  className,
}: CounterProps) {
  const reduced = useReducedMotionSafe();
  const [wrapRef, inView] = useInViewShared<HTMLSpanElement>();
  const valueRef = useRef<HTMLSpanElement>(null);

  const format = (value: number) => `${prefix}${value.toFixed(decimals)}${suffix}`;
  const final = format(to);

  useLayoutEffect(() => {
    const node = valueRef.current;
    if (!node) return;
    if (reduced) {
      node.textContent = final;
      return;
    }
    if (!inView) {
      // Pre-set the start value before the browser paints, so the real value
      // never flashes ahead of the animation.
      node.textContent = format(0);
      return;
    }

    let startedAt = 0;

    const stop = subscribeFrame((now) => {
      if (!startedAt) startedAt = now;
      const progress = Math.min(1, (now - startedAt) / (duration * 1000));
      node.textContent = format(to * easeEntrance(progress));
      if (progress === 1) stop();
    });

    return stop;
    // `format` is derived from the primitives already listed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decimals, duration, final, inView, prefix, reduced, suffix, to]);

  return (
    <span ref={wrapRef} className={className}>
      <span ref={valueRef} className="num" aria-hidden="true">
        {final}
      </span>
      <span className="sr-only">{final}</span>
    </span>
  );
}
