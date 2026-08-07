import { Plus, Trash2 } from "lucide-react";
import { useFieldArray, useForm } from "react-hook-form";

import { Button, Input, Select } from "@/components";

import type { ConfirmRequirementsPayload, JobDetail, Proficiency } from "../api/jobsApi";

const PROFICIENCY_OPTIONS = [
  { value: "novice", label: "Novice" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "expert", label: "Expert" },
];

const SENIORITY_OPTIONS = [
  { value: "entry", label: "Entry" },
  { value: "mid", label: "Mid" },
  { value: "senior", label: "Senior" },
];

interface FormValues {
  seniority: string;
  skills: { skill_name: string; min_proficiency: Proficiency; is_required: boolean; weight: number }[];
}

function buildInitial(detail: JobDetail): FormValues {
  // Prefer the *currently confirmed* requirements (re-editing a published
  // job) over the original LLM draft (first confirmation) — a re-edit must
  // never silently revert to what the model first guessed.
  if (detail.requirements.length > 0) {
    return {
      seniority: "mid",
      skills: detail.requirements.map((r) => ({
        skill_name: r.skill_name,
        min_proficiency: r.min_proficiency,
        is_required: r.is_required,
        weight: r.weight,
      })),
    };
  }
  const extracted = detail.extracted_requirements;
  if (extracted) {
    return {
      seniority: extracted.seniority,
      skills: [
        ...extracted.must_have_skills.map((s) => ({
          skill_name: s.name,
          min_proficiency: s.min_proficiency,
          is_required: true,
          weight: 1.0,
        })),
        ...extracted.desirable_skills.map((s) => ({
          skill_name: s.name,
          min_proficiency: s.min_proficiency,
          is_required: false,
          weight: 0.5,
        })),
      ],
    };
  }
  return { seniority: "mid", skills: [] };
}

interface RequirementsConfirmFormProps {
  detail: JobDetail;
  isSaving: boolean;
  onSubmit: (payload: ConfirmRequirementsPayload) => void;
}

/**
 * The MANDATORY confirmation screen — every field the LLM extracted,
 * editable, before anything reaches `job_requirements` or the matching
 * index. Nothing here is auto-saved; the recruiter must explicitly submit,
 * even to accept the draft verbatim, which is what stops a silent
 * extraction error from corrupting every subsequent match.
 */
export function RequirementsConfirmForm({ detail, isSaving, onSubmit }: RequirementsConfirmFormProps) {
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ defaultValues: buildInitial(detail) });

  const { fields, append, remove } = useFieldArray({ control, name: "skills" });

  return (
    <form
      className="space-y-5 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-6"
      onSubmit={handleSubmit((values) => onSubmit(values))}
    >
      <div>
        <h2 className="font-display text-lg font-semibold text-[var(--ink)]">Confirm requirements</h2>
        <p className="mt-1 text-sm text-[var(--slate)]">
          GroundTruth read these skills from your description. Review and edit before publishing — this
          job stays a draft candidates can't see until you confirm.
        </p>
      </div>

      <Select label="Overall seniority" options={SENIORITY_OPTIONS} {...register("seniority")} />

      <div className="space-y-2">
        {fields.map((field, index) => (
          <div key={field.id} className="flex flex-wrap items-end gap-2 rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-3">
            <div className="min-w-[10rem] flex-1">
              <Input
                label="Skill"
                error={errors.skills?.[index]?.skill_name?.message}
                {...register(`skills.${index}.skill_name` as const, { required: "Required" })}
              />
            </div>
            <div className="w-40">
              <Select
                label="Min. proficiency"
                options={PROFICIENCY_OPTIONS}
                {...register(`skills.${index}.min_proficiency` as const)}
              />
            </div>
            <label className="mb-1 flex items-center gap-1.5 text-xs text-[var(--slate)]">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-[var(--rule)] accent-[var(--violet)]"
                {...register(`skills.${index}.is_required` as const)}
              />
              Must-have
            </label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => remove(index)}
              aria-label={`Remove skill ${index + 1}`}
            >
              <Trash2 size={16} aria-hidden="true" />
            </Button>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() => append({ skill_name: "", min_proficiency: "intermediate", is_required: true, weight: 1 })}
      >
        <Plus size={14} aria-hidden="true" /> Add skill
      </Button>

      <div className="flex justify-end border-t border-[var(--rule)] pt-4">
        <Button type="submit" isLoading={isSaving} disabled={isSaving || fields.length === 0}>
          Confirm and publish
        </Button>
      </div>
    </form>
  );
}
