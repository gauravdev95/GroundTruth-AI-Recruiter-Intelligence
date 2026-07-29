import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useId, useMemo, useState } from "react";
import type { InputHTMLAttributes } from "react";

interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  error?: string;
  showStrengthMeter?: boolean;
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
const STRENGTH_COLORS = ["bg-red-500", "bg-orange-500", "bg-amber-400", "bg-lime-400", "bg-emerald-400"];

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(function PasswordInput(
  { label, error, showStrengthMeter = false, className, value, ...props },
  ref,
) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  const strength = useMemo(() => scorePassword(typeof value === "string" ? value : ""), [value]);

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-slate-700">
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
          className={
            className ??
            "w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 pr-11 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
          }
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-slate-700"
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
                  i < strength ? STRENGTH_COLORS[strength] : "bg-slate-200"
                }`}
              />
            ))}
          </div>
          <span className="text-xs text-slate-400">{STRENGTH_LABELS[strength]}</span>
        </div>
      ) : null}

      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-red-500">
          {error}
        </p>
      ) : null}
    </div>
  );
});
