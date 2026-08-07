import { cva } from "class-variance-authority";

/**
 * The button recipe, in its own module so `Button.tsx` exports a component and
 * nothing else — the `react-refresh/only-export-components` rule, and the
 * reason it exists: a file that exports both a component and a constant loses
 * fast refresh for the component.
 *
 * Exported because an `<a>` or a router `<Link>` that is visually a button
 * needs the real recipe rather than a hand-copied class string. Auth's "Back to
 * login" affordances are links — they navigate — and before this they each
 * carried their own `bg-ink … hover:bg-ink-hover`, which is how the product
 * ended up with primary buttons that disagreed with each other.
 *
 * Use `<Button>` for anything that performs an action; reach for this only
 * where the element genuinely has to be a link.
 *
 * NO `focus-visible:` RULES HERE, DELIBERATELY. `design/tokens.css` styles
 * `:focus-visible` globally with `--focus-ring`, and the product rule is one
 * ring on every focusable thing. This recipe previously drew its own in
 * `--verified` green, which broke that rule twice over: a second ring
 * implementation, and green spent on a UI state rather than on a proven claim.
 *
 * Weights stop at 600. `main.tsx` loads Inter at 400/500/600 only, so a
 * `font-bold` here does not get bolder type — it gets the browser's synthetic
 * emboldening of the 600 face, which smears the counters at button sizes.
 */
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-[var(--r-sm)] font-medium transition-[background-color,border-color,color,box-shadow] duration-150 disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        /*
         * The one place `--glow-a` is allowed to touch a control, per the
         * token file's rule 2 (backdrop, primary CTA fill, celebration). The
         * glow is a shadow rather than a background so the fill stays a flat
         * violet and the light reads as coming off it.
         */
        primary:
          "bg-[var(--violet)] text-white shadow-[0_2px_16px_-4px_rgb(var(--glow-a)/0.55)] hover:brightness-110 hover:shadow-[0_4px_22px_-4px_rgb(var(--glow-a)/0.7)]",
        secondary:
          "border border-[var(--rule)] bg-[var(--panel)] text-[var(--ink)] hover:border-[var(--violet)]/50 hover:bg-[var(--panel-raised)]",
        ghost: "text-[var(--slate)] hover:bg-[var(--panel)] hover:text-[var(--ink)]",
        /*
         * Outlined rather than filled, and for a contrast reason rather than a
         * stylistic one: `--failed` is #FF6B6B, and white on it is 2.5:1 —
         * below AA for any text size. As a tint with `--failed` as the
         * foreground it is 5.8:1 on `--bg` dark and 5.1:1 on white.
         *
         * `--failed` is borrowed here, not extended. The token means "an
         * operation did not complete"; this is "an action that destroys
         * something". They are different ideas that happen to share a colour,
         * and the alternative — minting a second red — would give the product
         * two danger colours that must never disagree.
         */
        destructive:
          "border border-[var(--failed)]/50 bg-[var(--failed)]/10 text-[var(--failed)] hover:border-[var(--failed)] hover:bg-[var(--failed)]/20",
      },
      size: {
        sm: "px-3 py-1.5 text-xs",
        md: "px-4 py-2.5 text-sm",
        lg: "px-5 py-3 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);
