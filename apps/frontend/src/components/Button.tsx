import { type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

import { buttonVariants } from "./buttonVariants";

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
}

/** The button. The variant recipe lives in `buttonVariants.ts` — see the note
 * there for the focus-ring and font-weight decisions. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, isLoading, disabled, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || isLoading}
      /*
       * Announced rather than only shown. The spinner below is aria-hidden, so
       * without this a screen-reader user gets a button that has silently
       * stopped responding.
       */
      aria-busy={isLoading || undefined}
      {...props}
    >
      {isLoading && (
        <span
          aria-hidden="true"
          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {/*
       * The label is not wrapped in a span that forces a colour. It used to be
       * — `!text-white` — which meant `secondary` and `ghost` rendered white
       * text on a near-white panel and were invisible in the light theme. The
       * colour belongs to the variant, and `border-current` above is what lets
       * the spinner inherit it instead of needing its own.
       */}
      {children}
    </button>
  );
});

Button.displayName = "Button";
