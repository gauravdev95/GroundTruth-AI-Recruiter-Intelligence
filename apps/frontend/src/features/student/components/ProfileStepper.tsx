import { cn } from "@/lib/utils";

import type { ProfileCompleteness, SectionCacheKey } from "../api/profileApi";
import { SECTIONS } from "../constants";
import { formSectionStatus } from "../lib/sectionScoring";
import { SectionBadges } from "./SectionBadges";

interface ProfileStepperProps {
  completeness: ProfileCompleteness;
  activeSection: SectionCacheKey;
  onSelect: (section: SectionCacheKey) => void;
}

/**
 * Every step is always reachable. The builder is explicitly a multi-sitting
 * flow, so gating later steps behind earlier ones would only stop a student
 * from filling in what they have to hand.
 */
export function ProfileStepper({ completeness, activeSection, onSelect }: ProfileStepperProps) {

  return (
    <nav aria-label="Profile sections">
      <ol className="space-y-1">
        {SECTIONS.map((meta, index) => {
          // One form can cover more than one scored section — `technical`
          // carries both GitHub and coding profiles. See `formSectionStatus`.
          const section = formSectionStatus(completeness, meta.key);
          const isActive = meta.key === activeSection;

          return (
            <li key={meta.key}>
              <button
                type="button"
                onClick={() => onSelect(meta.key)}
                aria-current={isActive ? "step" : undefined}
                className={cn(
                  "w-full rounded-xl border px-3 py-2.5 text-left transition",
                  isActive
                    ? "border-[var(--rule)] bg-[var(--panel)] shadow-sm"
                    : "border-transparent hover:border-[var(--rule)] hover:bg-[var(--panel)]/60",
                )}
              >
                <span className="flex items-start gap-2.5">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full font-mono text-[11px]",
                      isActive ? "bg-[var(--violet)] text-white" : "bg-[var(--rule)] text-[var(--slate)]",
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-[var(--ink)]">
                      {meta.title}
                      {meta.isMandatory ? <span className="ml-1 text-[var(--flagged)]">*</span> : null}
                    </span>
                    {section ? <span className="mt-1 block">{<SectionBadges section={section} />}</span> : null}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
