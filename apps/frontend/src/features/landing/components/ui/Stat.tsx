import { DURATION, useCountUp, useInViewShared } from "@/design/motion";

import type { Stat as StatContent } from "../../content/landing";

/**
 * One of §03's three figures, counting up when it scrolls into view.
 *
 * The count-up is driven by feeding `useCountUp` a target that flips from 0 to
 * the real value on intersection. That hook adopts its *first* value instantly
 * and animates every value after it, so mounting at 0 and then switching is
 * what produces the ramp — and it means a reader who never scrolls this far
 * never pays for an animation they did not see.
 *
 * `countTo: null` renders the figure as plain text. "1 in 4" has two numbers in
 * it and animating one while the other holds still looks like a bug.
 */
export function Stat({ value, countTo, suffix, label }: StatContent) {
  const [ref, inView] = useInViewShared<HTMLDivElement>();
  const counted = useCountUp(inView && countTo !== null ? countTo : 0, DURATION.count);

  const display =
    countTo === null ? value : `${Math.round(counted).toLocaleString("en-US")}${suffix ?? ""}`;

  return (
    <div ref={ref}>
      {/*
        `tabular-nums` stops the whole figure from twitching sideways as digits
        change width during the ramp, which is the difference between a number
        that counts and a number that vibrates.
      */}
      <p className="font-grotesk text-gt-stat font-bold tabular-nums text-gt-electric">{display}</p>
      <p className="mt-3 max-w-[280px] font-sans text-sm leading-relaxed text-gt-slate">{label}</p>
    </div>
  );
}
