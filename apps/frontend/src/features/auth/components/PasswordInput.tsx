import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useId, useMemo, useState } from "react";
import type { InputHTMLAttributes } from "react";

import { FIELD_TONE, type FieldTone } from "./fieldTone";

interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  error?: string;
  showStrengthMeter?: boolean;
  /** Which surface this sits on. See `fieldTone.ts`. */
  tone?: FieldTone;
}

function scorePassword(password: string): number {
  if (!password) return 0;
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^\w\s]/.test(password)) score += 1;
  return Math.min(score, 4);
}

const STRENGTH_LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"];

/**
 * The strength ramp runs red → amber → blue → violet, and deliberately never
 * reaches green.
 *
 * `--verified` means "proven by an artefact" everywhere else in this product,
 * and a strong password is not evidence of anything — it is a property of a
 * string the user just typed. Ending this ramp in green would be the first
 * thing a new user sees the colour do, and it would teach them the wrong
 * meaning for every verification badge they meet afterwards. It is the same
 * reasoning that keeps green off the resume-confidence badge and the profile
 * strength ring.
 *
 * Ending on `--violet` also matches the ring: brand colour for "how full",
 * status colour only for "how proven".
 */
const STRENGTH_COLORS = [
  "bg-[var(--failed)]",
  "bg-[var(--failed)]",
  "bg-[var(--flagged)]",
  "bg-[var(--blue)]",
  "bg-[var(--violet)]",
];

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(function PasswordInput(
  { label, error, showStrengthMeter = false, tone = "app", className, value, ...props },
  ref,
) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  const styles = FIELD_TONE[tone];
  const strength = useMemo(() => scorePassword(typeof value === "string" ? value : ""), [value]);

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <div className="relative">
        <input
          {...props}
          ref={ref}
          id={id}
          value={value}
          type={visible ? "text" : "password"}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={className ?? `${styles.input} pr-11`}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          className={`absolute right-3 top-1/2 -translate-y-1/2 ${styles.affordance}`}
        >
          {visible ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>

      {showStrengthMeter && typeof value === "string" && value.length > 0 ? (
        <div className="mt-1 flex items-center gap-2" aria-hidden="true">
          <div className="flex flex-1 gap-1">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  i < strength
                    ? STRENGTH_COLORS[strength]
                    : tone === "hero"
                      ? "bg-white/15"
                      : "bg-[var(--rule)]"
                }`}
              />
            ))}
          </div>
          <span
            className={tone === "hero" ? "text-xs text-white/50" : "text-xs text-[var(--muted)]"}
          >
            {STRENGTH_LABELS[strength]}
          </span>
        </div>
      ) : null}

      {error ? (
        <p id={`${id}-error`} role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
});
