import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary";
/** Which background the button is sitting on. Only `secondary` cares. */
type Tone = "light" | "dark";
type Size = "sm" | "md" | "lg";

interface ButtonProps {
  href: string;
  children: ReactNode;
  variant?: Variant;
  tone?: Tone;
  size?: Size;
  /**
   * Focus ring colour. Electric everywhere except the hero, where the scene
   * behind the buttons is already electric blue and a blue ring on it would be
   * invisible — which is the one thing a focus ring may never be.
   */
  ring?: "electric" | "ember";
  className?: string;
  /** Stretches to the column width. Used by the two pricing cards. */
  block?: boolean;
}

/**
 * Every call to action on the page.
 *
 * All of them are links — nothing on this page submits or mutates — so this
 * renders an `<a>` rather than a `<button>`. A `<button>` that navigates is a
 * keyboard bug: Enter and Space behave differently on it, and it does not
 * offer open-in-new-tab.
 *
 * Hover is a CSS transition rather than a Framer Motion variant. A spring on a
 * button costs frames for the entire duration of the hover, and the brief asks
 * for a 200ms lift, which is a transition by another name.
 */
export function Button({
  href,
  children,
  variant = "primary",
  tone = "light",
  size = "md",
  ring = "electric",
  className,
  block = false,
}: ButtonProps) {
  return (
    <a
      href={href}
      className={cn(
        "group inline-flex items-center justify-center gap-2 rounded-lg font-sans font-medium",
        "transition-[transform,background-color,border-color,box-shadow,color] duration-200 ease-out",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 motion-safe:hover:-translate-y-0.5",

        /* The offset colour has to match the surface, or the ring's gap shows
           as a pale halo on a black section. */
        tone === "dark"
          ? "focus-visible:ring-offset-gt-void"
          : "focus-visible:ring-offset-gt-paper",
        ring === "ember" ? "focus-visible:ring-gt-ember" : "focus-visible:ring-gt-electric",

        size === "sm" && "px-4 py-2 text-sm",
        size === "md" && "px-8 py-3.5 text-gt-body-sm",
        size === "lg" && "px-8 py-4 text-gt-body-sm",

        variant === "primary" && [
          "bg-gt-electric text-white",
          "hover:bg-[#1D4FD8]",
          /* The one shadow the brief permits, and only on the filled button. */
          "hover:shadow-[0_4px_24px_rgba(37,99,235,0.35)]",
        ],
        variant === "secondary" && [
          "border-[1.5px] bg-transparent",
          tone === "dark"
            ? "border-white/70 text-white hover:border-white hover:bg-white/5"
            : "border-gt-void/70 text-gt-void hover:border-gt-void hover:bg-gt-void/5",
        ],

        block && "w-full",
        className,
      )}
    >
      {children}
    </a>
  );
}
