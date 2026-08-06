import { ArrowRight, Check, Loader2 } from "lucide-react";

import { useToast } from "@/components";
import { useReducedMotionSafe } from "@/design/motion";
import { parseApiError } from "@/lib/apiError";
import { cn } from "@/lib/utils";

import { useSmartApply } from "../hooks/useApplications";

/**
 * Smart Apply, as one button that applies.
 *
 * ## Why this replaced a modal
 *
 * The previous implementation opened `SmartApplyModal` — an evidence preview
 * plus an optional cover-note textarea plus Cancel/Send. It was a reasonable
 * reading of "show the student what gets attached", but it broke the rule the
 * feature is named after: the verified profile *is* the application, so
 * applying is one click and zero forms. A modal makes it three interactions
 * and asks the student to compose something, which is the re-entry Smart
 * Apply exists to remove.
 *
 * What was actually load-bearing in that modal — *which* of your skills
 * matched — has moved to the card this button sits on, where the student
 * reads it **before** deciding rather than in a dialog after. Nothing that
 * informed the decision was lost; only the step between deciding and doing.
 *
 * ## The pulse
 *
 * A 2s glow loop, and the one piece of decoration on this surface. It runs
 * only on `emphasis` (the Tier B dashboard prompt), never in the job feed
 * list where several of these sit in a column and a row of pulsing buttons
 * would be noise rather than emphasis. It is a pure CSS animation on
 * `box-shadow` so it costs no frames on the shared rAF loop, and it is
 * dropped entirely under `prefers-reduced-motion` — a looping attention
 * animation is exactly what that setting is about.
 */
export function SmartApplyButton({
  jobId,
  jobTitle,
  companyName,
  emphasis = false,
  hasApplied = false,
  className,
}: {
  jobId: string;
  jobTitle: string;
  companyName: string;
  /** Tier B treatment: larger, pulsing. */
  emphasis?: boolean;
  hasApplied?: boolean;
  className?: string;
}) {
  const smartApply = useSmartApply();
  const { showToast } = useToast();
  const reduced = useReducedMotionSafe();

  if (hasApplied || smartApply.isSuccess) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-2 rounded-xl border border-verified/30 bg-verified/5 px-4 py-2.5 text-sm font-semibold text-verified",
          className,
        )}
      >
        <Check size={15} aria-hidden="true" />
        Applied
      </span>
    );
  }

  const apply = () => {
    smartApply.mutate(
      { jobId },
      {
        onSuccess: () =>
          // Names the company, because the confirmation has to tell the
          // student what they can now expect and from whom.
          showToast(`Applied! ${companyName} will review your evidence profile.`, "success"),
        onError: (error) =>
          showToast(parseApiError(error)?.message ?? "Could not apply to this job.", "error"),
      },
    );
  };

  return (
    <button
      type="button"
      onClick={apply}
      disabled={smartApply.isPending}
      aria-label={`Smart Apply to ${jobTitle} at ${companyName}`}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl bg-gt-electric font-semibold text-white",
        "transition hover:bg-gt-electric/90 focus-visible:outline focus-visible:outline-2",
        "focus-visible:outline-offset-2 focus-visible:outline-gt-electric disabled:opacity-70",
        emphasis ? "px-5 py-3 text-sm" : "px-4 py-2.5 text-[13px]",
        emphasis && !reduced && "animate-smart-apply-pulse",
        className,
      )}
    >
      {smartApply.isPending ? (
        <>
          <Loader2 size={15} className="animate-spin" aria-hidden="true" />
          Applying…
        </>
      ) : (
        <>
          Smart Apply
          <ArrowRight size={15} aria-hidden="true" />
        </>
      )}
    </button>
  );
}
