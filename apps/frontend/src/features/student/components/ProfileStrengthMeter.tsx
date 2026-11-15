import { ProgressRing, Surface } from "@/design";

import type { ProfileCompleteness } from "../api/profileApi";
import { SECTIONS } from "../constants";
import { formSectionStatus } from "../lib/sectionScoring";

/**
 * Live profile strength, server-computed. The number is never derived in the
 * browser — it arrives with every section save so it cannot drift from what
 * the database actually holds.
 *
 * Strength measures what is *filled*, not what is *verified*, which is why
 * the ring sweeps violet → blue and never green: an unverified profile at 100
 * is a real state, and the badges are where verification is communicated.
 * (An earlier version painted the bar `--verified` once the profile became
 * discoverable — the exact confusion this rule exists to prevent.)
 */
export function ProfileStrengthMeter({ completeness }: { completeness: ProfileCompleteness }) {
  const { profile_strength: strength } = completeness;

  return (
    <Surface as="section" aria-label="Profile strength" className="p-5">
      <div className="flex items-center gap-4">
        <ProgressRing value={strength} size={96} strokeWidth={8}>
          <span className="font-mono text-xl font-semibold tabular-nums text-[var(--ink)]">
            {strength}
            <span className="text-xs text-[var(--muted)]">/100</span>
          </span>
        </ProgressRing>
        <div className="min-w-0">
          <h2 className="font-display text-sm font-semibold text-[var(--ink)]">Profile strength</h2>
          <p className="mt-1 text-xs leading-relaxed text-[var(--slate)]">
            {completeness.is_discoverable
              ? "Discoverable — recruiters can find you."
              : completeness.meets_section_requirements
                ? "Requirements met — indexing is in progress."
                : "Complete the required sections to become discoverable."}
          </p>
        </div>
      </div>

      <dl className="mt-4 space-y-1.5 border-t border-[var(--rule-soft)] pt-4">
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

      <p className="mt-3 border-t border-[var(--rule-soft)] pt-3 text-xs text-[var(--slate)]">
        <span className="text-[var(--flagged)]">*</span> Required before recruiters can find you.
      </p>
    </Surface>
  );
}
