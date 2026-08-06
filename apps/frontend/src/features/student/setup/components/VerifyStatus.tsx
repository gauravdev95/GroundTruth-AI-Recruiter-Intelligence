import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

import type { VerifyOutcome } from "../api/setupApi";

/** What the Verify button has produced so far, for one field.
 *
 * `idle` is not an outcome the server can return — it is "nothing has been
 * checked yet", which the UI must not draw as a failure. Keeping it in the
 * same union as the three server outcomes is what stops a component from
 * having to carry both a status and a "has run" boolean and getting the
 * combination wrong. */
export type VerifyState = { phase: "idle" } | { phase: "checking" } | { phase: "done"; outcome: VerifyOutcome; message: string };

const PRESENTATION = {
  verified: {
    Icon: CheckCircle2,
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    label: "Verified",
  },
  // Amber, not green. The profile page resolved; nobody proved it is theirs.
  // Colouring this like a pass is the single most misleading thing this
  // component could do — see `live_checks.py`.
  unconfirmed: {
    Icon: AlertTriangle,
    className: "border-amber-200 bg-amber-50 text-amber-700",
    label: "Found, not confirmed",
  },
  failed: {
    Icon: XCircle,
    className: "border-red-200 bg-red-50 text-red-700",
    label: "Not found",
  },
} as const;

export function VerifyStatus({ state }: { state: VerifyState }) {
  if (state.phase === "idle") return null;

  if (state.phase === "checking") {
    return (
      <p
        role="status"
        className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600"
      >
        <Loader2 size={13} aria-hidden="true" className="animate-spin" />
        Verifying…
      </p>
    );
  }

  const { Icon, className, label } = PRESENTATION[state.outcome];

  return (
    <p
      // `alert` rather than `status` for a failure: it is the one outcome the
      // student has to act on before the step will save.
      role={state.outcome === "failed" ? "alert" : "status"}
      className={cn(
        "mt-2 inline-flex flex-wrap items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium",
        className,
      )}
    >
      <Icon size={13} aria-hidden="true" />
      <span className="font-semibold">{label}</span>
      <span className="font-normal opacity-90">— {state.message}</span>
    </p>
  );
}
