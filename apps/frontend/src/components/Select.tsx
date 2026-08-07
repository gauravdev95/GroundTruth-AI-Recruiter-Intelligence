import { ChevronDown } from "lucide-react";
import { forwardRef, useId } from "react";
import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

/**
 * Matches `Input` exactly — recessed onto `--surface`, hairline border, border
 * shift on focus and no second focus ring. The two must stay in step; a form
 * row where the select sits a shade off the text field beside it is the most
 * visible way a token migration goes wrong.
 *
 * `<option>` is styled by the OS, not by us. The explicit `bg-[var(--surface)]`
 * on each option is the one hook browsers honour, and it is the difference
 * between an open dropdown that matches the app and one that drops a white
 * list onto a dark page.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, options, placeholder, className, id, ...props },
  ref,
) {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={selectId} className="text-sm font-medium text-[var(--slate)]">
          {label}
        </label>
      ) : null}
      <div className="relative">
        <select
          {...props}
          ref={ref}
          id={selectId}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${selectId}-error` : undefined}
          className={cn(
            "w-full appearance-none rounded-[var(--r-sm)] border bg-[var(--surface)] px-4 py-2.5 pr-9 text-sm text-[var(--ink)]",
            "transition-colors duration-150",
            "border-[var(--rule)] focus:border-[var(--violet)]",
            "aria-[invalid=true]:border-[var(--failed)]",
            className,
          )}
        >
          {placeholder ? (
            <option value="" disabled className="bg-[var(--surface)] text-[var(--muted)]">
              {placeholder}
            </option>
          ) : null}
          {options.map((option) => (
            <option
              key={option.value}
              value={option.value}
              className="bg-[var(--surface)] text-[var(--ink)]"
            >
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted)]"
        />
      </div>
      {error ? (
        <p id={`${selectId}-error`} role="alert" className="text-xs text-[var(--failed)]">
          {error}
        </p>
      ) : null}
    </div>
  );
});
