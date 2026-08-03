import { motion } from "framer-motion";

import { DURATION, EASE, STAGGER, useInViewShared, useReducedMotionSafe } from "../lib/motion";

const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

interface OdometerProps {
  value: number;
  className?: string;
}

/**
 * A rolling-digit counter.
 *
 * Each digit position is a strip of 0–9 inside a one-line clipping box, moved by
 * `translateY(-n * 10%)`. Percentage translation is relative to the strip's own
 * height, so nothing needs measuring and no `top` or `height` is ever animated —
 * one composited transform per column.
 *
 * Columns start from the right so the last digit settles first, which reads as a
 * mechanical counter coming to rest rather than four independent spinners.
 */
export function Odometer({ value, className }: OdometerProps) {
  const reduced = useReducedMotionSafe();
  const [ref, inView] = useInViewShared<HTMLSpanElement>();
  const digits = String(Math.round(value)).split("");

  return (
    <span ref={ref} className={className}>
      <span className="odo num" aria-hidden="true">
        {digits.map((digit, index) => (
          <span className="odo-col" key={`${index}-${digit}`}>
            <motion.span
              className="odo-strip"
              initial={{ y: reduced ? `-${Number(digit) * 10}%` : "0%" }}
              animate={{ y: inView ? `-${Number(digit) * 10}%` : "0%" }}
              transition={{
                duration: reduced ? 0 : DURATION.cinematic,
                ease: EASE.entrance,
                // Rightmost column leads; each one to its left lags a beat.
                delay: reduced ? 0 : (digits.length - 1 - index) * STAGGER.siblings,
              }}
            >
              {DIGITS.map((candidate) => (
                <span className="odo-digit" key={candidate}>
                  {candidate}
                </span>
              ))}
            </motion.span>
          </span>
        ))}
      </span>
      <span className="sr-only">{value}</span>
    </span>
  );
}
