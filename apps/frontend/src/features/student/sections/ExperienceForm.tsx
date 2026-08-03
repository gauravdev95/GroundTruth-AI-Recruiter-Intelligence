import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";

import { Button, Input, Select, useToast } from "@/components";

import type { ExperiencesSection, SectionStatus } from "../api/profileApi";
import { VerificationBadge } from "../components/SectionBadges";
import { SectionShell } from "../components/SectionShell";
import { TechnologiesField } from "../components/TechnologiesField";
import { EMPLOYMENT_TYPE_OPTIONS, SECTIONS } from "../constants";
import { useSaveExperiences } from "../hooks/useProfileSection";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";
import {
  experiencesSchema,
  type ExperiencesForm as ExperiencesFormValues,
} from "../schemas/profileSchemas";

const META = SECTIONS[4];

interface ExperienceFormProps {
  data: ExperiencesSection;
  status: SectionStatus | undefined;
}

function toDefaults(data: ExperiencesSection): ExperiencesFormValues {
  return {
    experiences: data.experiences.map((experience) => ({
      company_name: experience.company_name,
      title: experience.title,
      employment_type: experience.employment_type,
      start_date: experience.start_date,
      end_date: experience.end_date,
      description: experience.description ?? "",
      technologies: experience.technologies,
    })),
  } as ExperiencesFormValues;
}

export function ExperienceForm({ data, status }: ExperienceFormProps) {
  const save = useSaveExperiences();
  const { showToast } = useToast();

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ExperiencesFormValues>({
    resolver: zodResolver(experiencesSchema),
    defaultValues: toDefaults(data),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "experiences" });

  useEffect(() => {
    reset(toDefaults(data));
  }, [data, reset]);

  const onSubmit = handleSubmit((values) => {
    save.mutate(
      {
        experiences: values.experiences.map((experience) => ({
          ...experience,
          description: experience.description?.trim() ? experience.description : null,
        })),
      },
      { onSuccess: () => showToast("Experience saved.", "success") },
    );
  });

  return (
    <SectionShell
      meta={META}
      status={status}
      onSubmit={onSubmit}
      isSaving={save.isPending}
      errorMessage={save.isError ? getProfileErrorMessage(save.error) : null}
    >
      {fields.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule bg-panel px-4 py-6 text-center text-sm text-slate-500">
          No experience recorded yet.
        </p>
      ) : null}

      {fields.map((field, index) => {
        const existing = data.experiences[index];
        return (
        <div key={field.id} className="rounded-xl border border-rule bg-panel p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="font-mono text-xs text-slate-500">Entry {index + 1}</span>
            <div className="flex items-center gap-2">
              {existing ? <VerificationBadge status={existing.verification_status} /> : null}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => remove(index)}
                aria-label={`Remove entry ${index + 1}`}
              >
                <Trash2 size={16} aria-hidden="true" />
              </Button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Company"
                placeholder="Acme Corp"
                error={errors.experiences?.[index]?.company_name?.message}
                {...register(`experiences.${index}.company_name` as const)}
              />
              <Input
                label="Role"
                placeholder="Backend Engineering Intern"
                error={errors.experiences?.[index]?.title?.message}
                {...register(`experiences.${index}.title` as const)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <Select
                label="Type"
                options={EMPLOYMENT_TYPE_OPTIONS}
                error={errors.experiences?.[index]?.employment_type?.message}
                {...register(`experiences.${index}.employment_type` as const)}
              />
              <Input
                type="date"
                label="Start date"
                error={errors.experiences?.[index]?.start_date?.message}
                {...register(`experiences.${index}.start_date` as const)}
              />
              <Input
                type="date"
                label="End date"
                error={errors.experiences?.[index]?.end_date?.message}
                {...register(`experiences.${index}.end_date` as const)}
              />
            </div>
            <p className="-mt-2 text-xs text-slate-500">Leave the end date empty if this is ongoing.</p>

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={`experience-description-${index}`}
                className="text-sm font-medium text-slate-700"
              >
                What you worked on (optional)
              </label>
              <textarea
                id={`experience-description-${index}`}
                rows={3}
                className="w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
                {...register(`experiences.${index}.description` as const)}
              />
            </div>

            <Controller
              control={control}
              name={`experiences.${index}.technologies` as const}
              render={({ field: techField }) => (
                <TechnologiesField
                  value={techField.value ?? []}
                  onChange={techField.onChange}
                  error={errors.experiences?.[index]?.technologies?.message}
                />
              )}
            />
          </div>
        </div>
        );
      })}

      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() =>
          append({
            company_name: "",
            title: "",
            employment_type: "internship",
            start_date: "",
            end_date: null,
            description: "",
            technologies: [],
          })
        }
      >
        <Plus size={14} aria-hidden="true" /> Add experience
      </Button>

      <p className="rounded-xl border border-rule bg-panel px-3 py-2 text-xs text-slate-500">
        Experience is self-reported — there is no external record to check it against. GroundTruth looks
        for weak internal corroboration (a company already known to the platform, technologies that
        overlap with your verified repositories) and flags entries it finds support for, but this can
        never reach a full "verified" state the way a repository or coding-platform account can.
      </p>
    </SectionShell>
  );
}
