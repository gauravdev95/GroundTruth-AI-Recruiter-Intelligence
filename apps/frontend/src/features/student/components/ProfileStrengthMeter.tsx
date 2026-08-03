import { cn } from "@/lib/utils";

import type { ProfileCompleteness } from "../api/profileApi";
import { SECTIONS } from "../constants";

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
  const { profile_strength: strength, sections } = completeness;
  const byKey = new Map(sections.map((section) => [section.key, section]));

  return (
    <div className="rounded-2xl border border-rule bg-panel p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-sm font-semibold text-ink">Profile strength</h2>
        <p className="font-mono text-2xl font-semibold tabular-nums text-ink">
          {strength}
          <span className="text-base text-slate-400">/100</span>
        </p>
      </div>

      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full bg-rule"
        role="progressbar"
        aria-valuenow={strength}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Profile strength"
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500 ease-out",
            completeness.is_discoverable ? "bg-verified" : "bg-ink",
          )}
          style={{ width: `${strength}%` }}
        />
      </div>

      <dl className="mt-4 space-y-1.5">
        {SECTIONS.map((meta) => {
          const section = byKey.get(meta.key);
          if (!section) return null;
          return (
            <div key={meta.key} className="flex items-center justify-between gap-3 text-xs">
              <dt className="truncate text-slate-600">
                {meta.title}
                {meta.isMandatory ? <span className="ml-1 text-flagged">*</span> : null}
              </dt>
              <dd className="shrink-0 font-mono tabular-nums text-slate-500">
                {section.points_earned}/{section.points_possible}
              </dd>
            </div>
          );
        })}
      </dl>

      <p className="mt-3 border-t border-rule pt-3 text-xs text-slate-500">
        <span className="text-flagged">*</span> Required before recruiters can find you.
      </p>
    </div>
  );
}
