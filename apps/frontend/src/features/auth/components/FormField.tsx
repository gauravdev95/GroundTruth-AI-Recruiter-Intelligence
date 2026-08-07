import { forwardRef, useId } from "react";
import type { InputHTMLAttributes } from "react";

import { FIELD_TONE, type FieldTone } from "./fieldTone";

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  /** Which surface this sits on. See `fieldTone.ts`. */
  tone?: FieldTone;
}

export const FormField = forwardRef<HTMLInputElement, FormFieldProps>(function FormField(
  { label, error, tone = "app", className, ...props },
  ref,
) {
  const id = useId();
  const styles = FIELD_TONE[tone];

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <input
        {...props}
        ref={ref}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={className ?? styles.input}
      />
      {error ? (
        <p id={`${id}-error`} role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
});
