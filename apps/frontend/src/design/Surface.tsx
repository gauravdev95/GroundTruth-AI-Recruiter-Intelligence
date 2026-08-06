import type { ReactNode } from "react";

import { DURATION, EASE, useReducedMotionSafe } from "./motion";

/**
 * The card. One component, three elevations, used everywhere in the app.
 *
 * WHY THE GLASS IS RESTRAINED
 *
 * `--panel` is translucent (70% dark / 78% light) so the fixed backdrop
 * passes behind every card. That is the entire glass effect and it is
 * deliberately the whole of it: no blurred-white overlays, no inner
 * highlights, no layered borders. The translucency exists for one structural
 * reason — it stops a long scrolling dashboard from reading as a stack of
 * identical rectangles — and once that job is done, more glass is cost
 * without benefit. Heavy backdrop blur is also the single most expensive
 * thing you can put on a scrolling list, and this product puts twenty cards
 * on a dashboard.
 *
 * `backdrop-blur` is applied at `sm` (4px) rather than the `xl` that reads
 * as "glassmorphism" in a screenshot. At 4px the backdrop is legible as
 * *light* behind the card; at 24px it is mud, and it costs a compositor
 * layer per card.
 */

type Elevation = "flat" | "raised" | "floating";

const ELEVATION: Record<Elevation, string> = {
  // The default. Hairline structure, no shadow — depth comes from the
  // backdrop showing through.
  flat: "bg-[var(--panel)] border border-[var(--rule)] shadow-none",
  // Cards that are the primary object on their screen.
  raised: "bg-[var(--panel)] border border-[var(--rule)] shadow-[var(--shadow-panel)]",
  // Menus, popovers, modals. Opaque, because a floating surface can overlap
  // arbitrary content and translucency there is unreadable rather than airy.
  floating: "bg-[var(--panel-raised)] border border-[var(--rule)] shadow-[var(--shadow-raised)]",
};

interface SurfaceProps {
  children: ReactNode;
  elevation?: Elevation;
  /** Lifts and brightens the hairline on hover. Only for cards that are links. */
  interactive?: boolean;
  /** Violet hairline + glow. For the one card on screen that is selected. */
  selected?: boolean;
  className?: string;
  as?: "div" | "article" | "section" | "li" | "label";
}

export function Surface({
  children,
  elevation = "flat",
  interactive = false,
  selected = false,
  className = "",
  as: Component = "div",
}: SurfaceProps) {
  const reduced = useReducedMotionSafe();

  return (
    <Component
      className={[
        "rounded-[var(--r-lg)] backdrop-blur-sm",
        ELEVATION[elevation],
        interactive && "cursor-pointer hover:border-[var(--violet)]/40 hover:-translate-y-0.5",
        selected && "border-[var(--violet)] shadow-[0_0_0_1px_var(--violet),var(--shadow-panel)]",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={
        reduced
          ? undefined
          : {
              transition: `transform ${DURATION.fast}s cubic-bezier(${EASE.standard.join(
                ",",
              )}), border-color ${DURATION.fast}s ease, box-shadow ${DURATION.fast}s ease`,
            }
      }
    >
      {children}
    </Component>
  );
}

/**
 * The ambient backdrop — three brand-light blooms on the app background.
 *
 * Fixed and `pointer-events-none`, rendered once at the app shell rather than
 * per route, so it does not restart on navigation. Blooms are static:
 * animating them would put three large composited layers on a permanent rAF
 * loop behind every screen in the product, which is the most expensive
 * possible way to add almost nothing.
 *
 * This is the only place `--glow-*` touches the page outside a CTA fill and
 * a celebration burst, per the token file's rule 2.
 */
export function Backdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div
        className="absolute -left-[10%] -top-[15%] h-[55vh] w-[55vh] rounded-full blur-[120px]"
        style={{ background: "rgb(var(--glow-a) / 0.16)" }}
      />
      <div
        className="absolute -right-[15%] top-[25%] h-[50vh] w-[50vh] rounded-full blur-[120px]"
        style={{ background: "rgb(var(--glow-b) / 0.12)" }}
      />
      <div
        className="absolute bottom-[-20%] left-[30%] h-[45vh] w-[45vh] rounded-full blur-[120px]"
        style={{ background: "rgb(var(--glow-c) / 0.08)" }}
      />
    </div>
  );
}
