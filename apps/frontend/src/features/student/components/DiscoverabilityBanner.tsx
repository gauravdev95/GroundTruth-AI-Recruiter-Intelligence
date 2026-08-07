import { CheckCircle2, Info, Loader2 } from "lucide-react";

import type { ProfileCompleteness } from "../api/profileApi";

/**
 * States explicitly what is still required before the profile becomes
 * discoverable, listing the exact missing items the server reported rather
 * than a vague "complete your profile" nudge.
 *
 * `blocking` only ever contains items from the two mandatory sections — the
 * optional sections raise strength but never gate discoverability, so they are
 * deliberately absent here.
 *
 * Three states, not two. `meets_section_requirements && !is_discoverable` is
 * the indexing window: the student has done everything they can and the
 * embedding worker has not finished. Showing the "still needed" banner there
 * would list an empty set of requirements and imply the student is at fault
 * for a delay that is entirely ours.
 */
export function DiscoverabilityBanner({ completeness }: { completeness: ProfileCompleteness }) {
  if (!completeness.is_discoverable && completeness.meets_section_requirements) {
    return (
      <div className="flex items-start gap-3 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-4" role="status">
        <Loader2 size={18} className="mt-0.5 shrink-0 animate-spin text-[var(--muted)]" aria-hidden="true" />
        <div className="text-sm">
          <p className="font-medium text-[var(--ink)]">Indexing your profile…</p>
          <p className="mt-0.5 text-[var(--slate)]">
            Both required sections are complete. We're building your profile's search index now — you'll
            appear in recruiter results and start seeing job matches as soon as it finishes. Nothing else
            is needed from you.
          </p>
        </div>
      </div>
    );
  }

  if (completeness.is_discoverable) {
    return (
      <div
        className="flex items-start gap-3 rounded-2xl border border-[var(--verified)]/30 bg-[var(--verified)]/10 p-4"
        role="status"
      >
        <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-[var(--verified)]" aria-hidden="true" />
        <div className="text-sm">
          <p className="font-medium text-[var(--ink)]">Your profile is discoverable.</p>
          <p className="mt-0.5 text-[var(--slate)]">
            Recruiters can find you in search. Adding projects, certificates and experience raises your
            profile strength — your listed accounts are checked separately, and verification badges appear
            as those checks complete.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex items-start gap-3 rounded-2xl border border-[var(--flagged)]/30 bg-[var(--flagged)]/10 p-4"
      role="status"
    >
      <Info size={18} className="mt-0.5 shrink-0 text-[var(--flagged)]" aria-hidden="true" />
      <div className="text-sm">
        <p className="font-medium text-[var(--ink)]">Your profile is not discoverable yet.</p>
        <p className="mt-0.5 text-[var(--slate)]">
          Recruiters cannot find you until Basic Information and Technical Verification are both complete.
          Still needed:
        </p>
        <ul className="mt-2 list-inside list-disc space-y-0.5 text-[var(--slate)]">
          {completeness.blocking.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
