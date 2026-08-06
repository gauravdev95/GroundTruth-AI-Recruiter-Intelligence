import { Loader2 } from "lucide-react";

import { useMagnetic } from "@/design/motion";
import { cn } from "@/lib/utils";

interface HeroSubmitProps {
  pending: boolean;
  /** Rest label. */
  children: string;
  /** Label while the request is in flight. */
  pendingLabel: string;
}

/**
 * The primary action on the sign-in and sign-up forms.
 *
 * MAGNETISM, AND WHY NOTHING ELSE HERE ANIMATES `transform`. `useMagnetic` is
 * the product's existing pointer micro-interaction (`design/motion.ts`) and it
 * works by writing `element.style.transform` directly, releasing through a CSS
 * transition so letting go costs no frames. That makes it the sole owner of
 * this element's transform: a Tailwind `active:scale-95`, or a Framer
 * `whileTap`, would be a second writer to the same property and the two would
 * clobber each other mid-gesture. The press is therefore expressed as a
 * brightness and shadow change instead, which is a different property and
 * reads just as clearly.
 *
 * The hook no-ops under `prefers-reduced-motion` and on touch-primary devices,
 * so this is a plain button in both cases.
 *
 * `disabled` while pending is what makes double-submit impossible; the spinner
 * only explains why. Both matter — a spinner on a still-clickable button is a
 * decoration over a race.
 */
export function HeroSubmit({ pending, children, pendingLabel }: HeroSubmitProps) {
  const ref = useMagnetic<HTMLButtonElement>();

  return (
    <button
      ref={ref}
      type="submit"
      disabled={pending}
      className={cn(
        "mt-1 flex w-full items-center justify-center gap-2 rounded-lg bg-gt-electric px-4 py-3",
        "font-sans text-sm font-semibold text-white",
        "transition-[background-color,box-shadow,filter,opacity] duration-200 ease-out",
        "shadow-[0_6px_24px_-6px_rgba(37,99,235,0.6)]",
        "hover:bg-[#1D4FD8] hover:shadow-[0_10px_34px_-6px_rgba(37,99,235,0.75)]",
        "active:brightness-90 active:shadow-[0_3px_14px_-6px_rgba(37,99,235,0.7)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A1128]",
        "disabled:cursor-not-allowed disabled:opacity-70 disabled:shadow-none",
      )}
    >
      {pending ? (
        <>
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          {pendingLabel}
        </>
      ) : (
        children
      )}
    </button>
  );
}
