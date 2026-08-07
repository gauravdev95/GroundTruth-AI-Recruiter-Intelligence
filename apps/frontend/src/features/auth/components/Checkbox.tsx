import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

import { FIELD_TONE, type FieldTone } from "./fieldTone";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  error?: string;
  /** Which surface this sits on. See `fieldTone.ts`. */
  tone?: FieldTone;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, error, tone = "app", ...props },
  ref,
) {
  const id = useId();
  const styles = FIELD_TONE[tone];

  return (
    <div>
      <label htmlFor={id} className={styles.checkboxLabel}>
        <input
          {...props}
          ref={ref}
          id={id}
          type="checkbox"
          aria-invalid={Boolean(error)}
          className={styles.checkbox}
        />
        <span>{label}</span>
      </label>
      {error ? (
        <p role="alert" className={`mt-1 ${styles.error}`}>
          {error}
        </p>
      ) : null}
    </div>
  );
});
