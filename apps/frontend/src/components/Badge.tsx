import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * The status chip.
 *
 * EVERY VARIANT IS A TINT PLUS A FULL-STRENGTH FOREGROUND, never a pale fill
 * with dark text. The old set (`bg-emerald-100 text-emerald-700`) only worked
 * on a white page; on `--bg` a 100-weight fill is a bright block that outshouts
 * the content it annotates. A 12%-alpha tint of the status colour reads as the
 * same chip in both themes and needs no per-theme override, because the token
 * underneath it already has one.
 *
 * `success` IS NOT A GENERAL-PURPOSE GREEN. It is `--verified`, and the token
 * file's rule 1 governs it: green means "proven by an artefact". A chip that
 * says "Active" or "Saved" is `neutral` or `info`, not `success` — spending
 * green on a save confirmation devalues every honest verification badge beside
 * it. `warning` is `--flagged` ("claimed, unchecked"), and `danger` is
 * `--failed` ("this operation did not complete"), which is a different idea
 * from either.
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        neutral: "bg-[var(--panel-raised)] text-[var(--slate)]",
        success: "bg-[var(--verified)]/12 text-[var(--verified)]",
        warning: "bg-[var(--flagged)]/12 text-[var(--flagged)]",
        danger: "bg-[var(--failed)]/12 text-[var(--failed)]",
        info: "border border-[var(--rule)] bg-[var(--panel)] text-[var(--ink)]",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
