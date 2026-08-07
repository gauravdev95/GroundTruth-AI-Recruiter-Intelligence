import { cn } from "@/lib/utils";

import type { ProfileCompleteness } from "../api/profileApi";
import { SECTIONS } from "../constants";
import { formSectionStatus } from "../lib/sectionScoring";

/**
 * Live profile strength, server-computed. The number is never derived in the
 * browser — it arrives with every section save so it cannot drift from what
 * the database actually holds.
 *
 * Strength measures what is *filled*, not what is *verified*, which is why
 * this component shows no verification colour: an unverified profile at 100
 * is a real state, and the badges are where verification is communicated.
 */
export function ProfileStrengthMeter({ completeness }: { completeness: ProfileCompleteness }) {
  const { profile_strength: strength } = completeness;

  return (
    <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-sm font-semibold text-[var(--ink)]">Profile strength</h2>
        <p className="font-mono text-2xl font-semibold tabular-nums text-[var(--ink)]">
          {strength}
          <span className="text-base text-[var(--muted)]">/100</span>
        </p>
      </div>

      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--rule)]"
        role="progressbar"
        aria-valuenow={strength}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Profile strength"
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500 ease-out",
            completeness.is_discoverable ? "bg-[var(--verified)]" : "bg-[var(--violet)]",
          )}
          style={{ width: `${strength}%` }}
        />
      </div>

      <dl className="mt-4 space-y-1.5">
        {SECTIONS.map((meta) => {
          const section = formSectionStatus(completeness, meta.key);
          if (!section) return null;
          return (
            <div key={meta.key} className="flex items-center justify-between gap-3 text-xs">
              <dt className="truncate text-[var(--slate)]">
                {meta.title}
                {meta.isMandatory ? <span className="ml-1 text-[var(--flagged)]">*</span> : null}
              </dt>
              <dd className="shrink-0 font-mono tabular-nums text-[var(--slate)]">
                {section.points_earned}/{section.points_possible}
              </dd>
            </div>
          );
        })}
      </dl>

      <p className="mt-3 border-t border-[var(--rule)] pt-3 text-xs text-[var(--slate)]">
        <span className="text-[var(--flagged)]">*</span> Required before recruiters can find you.
      </p>
    </div>
  );
}
