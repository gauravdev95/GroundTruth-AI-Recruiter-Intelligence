import { useCallback, useRef, useState } from "react";
import type { MouseEvent, ReactNode, Ref } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link } from "react-router-dom";

import { DURATION, EASE, useIsTouch, useMagnetic, useReducedMotionSafe } from "../lib/motion";

interface MagneticButtonProps {
  children: ReactNode;
  /** Internal route. Renders a react-router `<Link>`. */
  to?: string;
  /** External URL. Renders an `<a>`. */
  href?: string;
  onClick?: () => void;
  /** `secondary` is the hairline variant — same geometry, no fill. */
  variant?: "primary" | "secondary";
  className?: string;
  /** Trailing arrow that slides on hover. Off for buttons that aren't a step. */
  arrow?: boolean;
  type?: "button" | "submit";
  disabled?: boolean;
  "aria-label"?: string;
}

interface Ripple {
  id: number;
  x: number;
  y: number;
}

/**
 * The page's single button primitive.
 *
 * Three behaviours, all of them transform-and-opacity only:
 *   - magnetic pull toward the pointer, capped at 6px by the shared hook
 *   - a ripple that starts at the actual click coordinates, scaled rather than
 *     grown, so no `width`/`height` is animated
 *   - an arrow that slides on hover
 *
 * All three are off on touch devices and under reduced motion, where they are
 * either meaningless or unwanted. `:focus-visible` is styled by the stylesheet
 * independently of `:hover`, so keyboard users get their own affordance rather
 * than a borrowed hover state.
 *
 * The gradient border in the brief's §8.5 is deliberately not implemented: this
 * page's design system paints no gradients, and that was agreed as a deviation.
 */
export function MagneticButton({
  children,
  to,
  href,
  onClick,
  variant = "primary",
  className = "",
  arrow = false,
  type = "button",
  disabled = false,
  "aria-label": ariaLabel,
}: MagneticButtonProps) {
  const reduced = useReducedMotionSafe();
  const touch = useIsTouch();
  const magneticRef = useMagnetic<HTMLElement>(6);
  const rippleId = useRef(0);
  const [ripples, setRipples] = useState<Ripple[]>([]);

  const effectsOn = !reduced && !touch;

  const spawnRipple = useCallback(
    (event: MouseEvent<HTMLElement>) => {
      if (!effectsOn) return;
      const box = event.currentTarget.getBoundingClientRect();
      const id = (rippleId.current += 1);
      setRipples((current) => [
        ...current,
        { id, x: event.clientX - box.left, y: event.clientY - box.top },
      ]);
    },
    [effectsOn],
  );

  const handleClick = useCallback(
    (event: MouseEvent<HTMLElement>) => {
      spawnRipple(event);
      onClick?.();
    },
    [onClick, spawnRipple],
  );

  const retireRipple = useCallback((id: number) => {
    setRipples((current) => current.filter((ripple) => ripple.id !== id));
  }, []);

  const classes = ["btn", variant === "secondary" ? "btn-2" : "", className]
    .filter(Boolean)
    .join(" ");

  const body = (
    <>
      <span className="btn-label">{children}</span>

      {arrow && (
        <span className="btn-arrow" aria-hidden="true">
          →
        </span>
      )}

      {/*
        Ripple layer. Each ripple is a fixed 12px dot positioned once at the
        click point and then scaled — animating a radius would animate `width`.
      */}
      <AnimatePresence>
        {ripples.map((ripple) => (
          <motion.span
            key={ripple.id}
            className="btn-ripple"
            aria-hidden="true"
            style={{ left: ripple.x - 6, top: ripple.y - 6 }}
            initial={{ scale: 0.4, opacity: 0.3 }}
            animate={{ scale: 26, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.slow, ease: EASE.exit }}
            onAnimationComplete={() => retireRipple(ripple.id)}
          />
        ))}
      </AnimatePresence>
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        className={classes}
        aria-label={ariaLabel}
        ref={magneticRef as Ref<HTMLAnchorElement>}
        onClick={handleClick}
      >
        {body}
      </Link>
    );
  }

  if (href) {
    return (
      <a
        href={href}
        className={classes}
        aria-label={ariaLabel}
        ref={magneticRef as Ref<HTMLAnchorElement>}
        onClick={handleClick}
      >
        {body}
      </a>
    );
  }

  return (
    <button
      type={type}
      className={classes}
      aria-label={ariaLabel}
      disabled={disabled}
      ref={magneticRef as Ref<HTMLButtonElement>}
      onClick={handleClick}
    >
      {body}
    </button>
  );
}
