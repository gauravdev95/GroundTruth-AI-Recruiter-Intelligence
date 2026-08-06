import { AlertTriangle } from "lucide-react";

import type { FieldTone } from "./fieldTone";

/**
 * The one place a form reports a failure that is not attached to a single
 * field.
 *
 * `aria-live="assertive"` is deliberate and is the exception rather than the
 * rule: a submit that failed has already cost the user an action and they may
 * have moved focus away from the form by the time the answer arrives.
 */
export function AlertBanner({ message, tone = "light" }: { message: string; tone?: FieldTone }) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={
        tone === "dark"
          ? // `red-200` rather than the light tone's `red-700`: on the hero's
            // darkest band that is the difference between ~2:1 and comfortably
            // past 4.5:1, on the one line the user most needs to be able to read.
            "flex items-start gap-2.5 rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200 backdrop-blur-sm animate-fade-in"
          : "flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 animate-fade-in"
      }
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
