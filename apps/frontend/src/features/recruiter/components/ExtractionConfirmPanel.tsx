import { ArrowLeft, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button, Select } from "@/components";

import type { ConfirmRequirementsPayload, JobDetail } from "../api/jobsApi";
import {
  buildExtractionDraft,
  toSkillPayloads,
  REVIEW_DWELL_MS,
  type ExtractionDraft,
} from "../lib/extractionDraft";
import { TagInput } from "./TagInput";

const SENIORITY_OPTIONS = [
  { value: "entry", label: "Entry" },
  { value: "mid", label: "Mid" },
  { value: "senior", label: "Senior" },
];

/**
 * Role type is LLM-inferred and stored on `extracted_requirements` (a JSONB
 * blob), not as a column with an enum behind it — so this list is the read
 * side's best guess at the vocabulary, and free text the model produced that
 * is not in it is preserved as an extra option rather than silently reset to
 * the first entry. Losing the model's answer because the dropdown had no slot
 * for it would be a confirmation screen that quietly changes what it is
 * asking the recruiter to confirm.
 */
const ROLE_TYPE_OPTIONS = [
  { value: "backend", label: "Backend" },
  { value: "frontend", label: "Frontend" },
  { value: "fullstack", label: "Full-stack" },
  { value: "mobile", label: "Mobile" },
  { value: "data", label: "Data" },
  { value: "ml", label: "ML / AI" },
  { value: "devops", label: "DevOps / Infrastructure" },
  { value: "qa", label: "QA" },
  { value: "other", label: "Other" },
];

export interface ExtractionConfirmPanelProps {
  detail: JobDetail;
  seedSkills: string[];
  isSaving: boolean;
  onBack: () => void;
  onConfirm: (payload: ConfirmRequirementsPayload) => void;
}

/**
 * Screen 2's right column — everything the extraction produced, editable, and
 * the gate that publishes it.
 *
 * Nothing here auto-saves. The recruiter submits explicitly even to accept
 * the draft verbatim, which is what stops a bad extraction from reaching the
 * matching index by inaction.
 */
export function ExtractionConfirmPanel({
  detail,
  seedSkills,
  isSaving,
  onBack,
  onConfirm,
}: ExtractionConfirmPanelProps) {
  const [state, setState] = useState<ExtractionDraft>(() => buildExtractionDraft(detail, seedSkills));
  const [dwellElapsed, setDwellElapsed] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDwellElapsed(true), REVIEW_DWELL_MS);
    return () => clearTimeout(timer);
  }, []);

  const roleTypeOptions = useMemo(() => {
    const known = ROLE_TYPE_OPTIONS.some((o) => o.value === state.roleType);
    return known
      ? ROLE_TYPE_OPTIONS
      : [{ value: state.roleType, label: state.roleType }, ...ROLE_TYPE_OPTIONS];
  }, [state.roleType]);

  const patch = (next: Partial<ExtractionDraft>) => setState((prev) => ({ ...prev, ...next }));

  // A job with no must-have skill matches on the semantic term alone, which
  // is not a requirement set — it is a search. Blocked here rather than
  // server-side because the server legitimately accepts requirement lists
  // that this *screen* should not produce.
  const hasRequirements = state.mustHave.length > 0;
  const canPublish = dwellElapsed && hasRequirements && !isSaving;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-5 p-5">
        <TagInput
          label="Must-have skills"
          value={state.mustHave}
          onChange={(mustHave) => patch({ mustHave })}
          hint="A candidate is scored on how much verified evidence they have for each of these."
        />

        <TagInput
          label="Nice-to-have skills"
          value={state.niceToHave}
          onChange={(niceToHave) => patch({ niceToHave })}
          hint="Counted at half weight. Never used to exclude anyone."
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Seniority"
            options={SENIORITY_OPTIONS}
            value={state.seniority}
            onChange={(event) => patch({ seniority: event.target.value })}
          />
          <Select
            label="Role type"
            options={roleTypeOptions}
            value={state.roleType}
            onChange={(event) => patch({ roleType: event.target.value })}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="location-constraint" className="text-sm font-medium text-slate-700">
            Location constraint
          </label>
          <input
            id="location-constraint"
            value={state.locationConstraint}
            onChange={(event) => patch({ locationConstraint: event.target.value })}
            placeholder="Bangalore, India"
            className="w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
          />
          <p className="text-xs text-slate-500">
            From your posting. Edit it here and you are editing the job — change the posting itself
            with “Back to edit”.
          </p>
        </div>

        {!hasRequirements ? (
          <p role="alert" className="rounded-lg border border-flagged/30 bg-flagged/10 px-3 py-2.5 text-xs text-flagged">
            Add at least one must-have skill. Without one, every candidate is ranked on the
            description’s wording alone.
          </p>
        ) : null}
      </div>

      <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border-t border-rule bg-white/95 px-5 py-4 backdrop-blur">
        <Button type="button" variant="secondary" onClick={onBack} disabled={isSaving}>
          <ArrowLeft size={15} aria-hidden="true" />
          Back to edit
        </Button>

        <div className="flex items-center gap-3">
          {!dwellElapsed ? (
            <span className="text-xs text-slate-400" aria-live="polite">
              Reviewing…
            </span>
          ) : null}
          <Button
            type="button"
            onClick={() => onConfirm({ seniority: state.seniority, skills: toSkillPayloads(state) })}
            disabled={!canPublish}
            isLoading={isSaving}
            className="bg-gt-electric hover:bg-gt-electric/90"
            title={dwellElapsed ? undefined : "Take a moment to read the extracted requirements"}
          >
            <ShieldCheck size={15} aria-hidden="true" />
            Confirm &amp; publish job
          </Button>
        </div>
      </div>
    </div>
  );
}
