import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded font-bold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-verified disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary:
          "bg-ink !text-white hover:bg-ink-hover",
        secondary:
          "border border-ink bg-transparent text-ink hover:bg-ink/5",
        ghost:
          "text-slate-600 hover:bg-slate-100",
        destructive:
          "bg-red-600 !text-white hover:bg-red-700",
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
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    { className, variant, size, isLoading, disabled, children, ...props },
    ref
  ) {
    return (
      <button
        ref={ref}
        className={cn(
          buttonVariants({ variant, size }),
          "font-bold",
          className
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && (
          <span
            aria-hidden="true"
            className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          />
        )}
        <span className="!text-white font-bold">
          {children}
        </span>
      </button>
    );
  }
);

Button.displayName = "Button";