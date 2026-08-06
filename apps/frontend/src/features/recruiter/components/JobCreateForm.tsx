import { AlertTriangle, ArrowRight } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button, Input, Select } from "@/components";
import { cn } from "@/lib/utils";

import type { ExperienceLevel, JobCreatePayload, JobType } from "../api/jobsApi";
import { TagInput } from "./TagInput";

/* ==================================================================
   FIELD VOCABULARY — where the form's options meet the API's enums
   ================================================================== */

/**
 * The recruiter-facing experience bands, and what each one actually persists.
 *
 * `job_postings.experience_level` has three values, not four
 * (`domains/recruiter/models.py::ExperienceLevel`), so the top two bands both
 * map to `senior`. That is a lossy mapping and it is surfaced rather than
 * hidden: `warning` below is shown the moment either is picked, because on a
 * student platform `senior` matches **zero** candidates by design —
 * `matching/service.py::_graduation_year_window` returns `None` for it, since
 * `candidate_profiles` has no years-of-experience field and guessing one from
 * a proxy would be inventing data. A recruiter who picks "5+ yrs" and gets an
 * empty board deserves to have been told why before they published.
 */
const EXPERIENCE_BANDS: {
  value: string;
  label: string;
  level: ExperienceLevel;
  warning?: string;
}[] = [
  { value: "fresher", label: "Fresher", level: "entry" },
  { value: "1-3", label: "1–3 yrs", level: "mid" },
  {
    value: "3-5",
    label: "3–5 yrs",
    level: "senior",
    warning:
      "GroundTruth matches students and new graduates, who do not report years of professional experience. Roles above the 1–3 band will not match any candidate today.",
  },
  {
    value: "5+",
    label: "5+ yrs",
    level: "senior",
    warning:
      "GroundTruth matches students and new graduates, who do not report years of professional experience. Roles above the 1–3 band will not match any candidate today.",
  },
];

/**
 * Work mode. `job_postings` stores a boolean `is_remote`, so Hybrid and
 * Onsite are the *same* stored value and differ only in the copy shown on
 * this form. Both require a location, which is the part that actually
 * changes matching behaviour (`_prefiltered_candidate_ids` filters on it),
 * so the distinction the recruiter cares about — "is there a place I need
 * you to be" — is preserved even though the label is not.
 */
const WORK_MODES: { value: string; label: string; isRemote: boolean; needsLocation: boolean }[] = [
  { value: "remote", label: "Remote", isRemote: true, needsLocation: false },
  { value: "hybrid", label: "Hybrid", isRemote: false, needsLocation: true },
  { value: "onsite", label: "Onsite", isRemote: false, needsLocation: true },
];

const JOB_TYPE_OPTIONS = [
  { value: "full_time", label: "Full-time" },
  { value: "internship", label: "Internship" },
  { value: "contract", label: "Contract" },
  { value: "part_time", label: "Part-time" },
];

/** Seeds the city autocomplete. A `<datalist>`, not a combobox: it suggests
 * without constraining, which is what "city-level autocomplete" has to mean
 * for a field whose real domain is every city on earth. */
const COMMON_LOCATIONS = [
  "Bangalore, India",
  "Hyderabad, India",
  "Pune, India",
  "Chennai, India",
  "Mumbai, India",
  "Delhi NCR, India",
  "Kolkata, India",
  "Ahmedabad, India",
  "Jaipur, India",
  "Kochi, India",
];

export const TITLE_MAX = 80;
export const DESCRIPTION_MIN = 100;
export const MIN_SKILLS = 3;

/** Thirty days out, in the `yyyy-mm-dd` an `<input type="date">` requires. */
function defaultDeadline(): string {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  return date.toISOString().slice(0, 10);
}

interface FormValues {
  title: string;
  description: string;
  skills: string[];
  band: string;
  jobType: JobType;
  location: string;
  workMode: string;
  deadline: string;
}

export interface JobDraft {
  payload: JobCreatePayload;
  /** Carried to the confirmation screen rather than posted here. See
   * `JobCreatePage` for why they cannot travel with the job itself. */
  seedSkills: string[];
}

export interface JobCreateFormProps {
  isSaving: boolean;
  onSubmit: (draft: JobDraft) => void;
}

/**
 * Screen 1 — the recruiter-authored half of a posting.
 *
 * The submit button says "Extract Requirements", not "Publish", and it means
 * it: this creates a **draft** and hands it to the LLM extraction task. The
 * job becomes visible to candidates only after a human confirms what came
 * back (`/recruiter/jobs/:id/confirm`). There is no path from this form to a
 * published job, which is enforced server-side too — `confirm_job` is the
 * only writer of `JobStatus.PUBLISHED`.
 */
export function JobCreateForm({ isSaving, onSubmit }: JobCreateFormProps) {
  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      title: "",
      description: "",
      skills: [],
      band: "fresher",
      jobType: "full_time",
      location: "",
      workMode: "onsite",
      deadline: defaultDeadline(),
    },
  });

  const [descriptionLength, setDescriptionLength] = useState(0);
  const title = watch("title");
  const band = EXPERIENCE_BANDS.find((b) => b.value === watch("band")) ?? EXPERIENCE_BANDS[0];
  const workMode = WORK_MODES.find((m) => m.value === watch("workMode")) ?? WORK_MODES[2];

  const submit = handleSubmit((values) => {
    const mode = WORK_MODES.find((m) => m.value === values.workMode) ?? WORK_MODES[2];
    const level = EXPERIENCE_BANDS.find((b) => b.value === values.band) ?? EXPERIENCE_BANDS[0];
    onSubmit({
      payload: {
        title: values.title.trim(),
        description: values.description.trim(),
        job_type: values.jobType,
        experience_level: level.level,
        location: mode.isRemote ? null : values.location.trim() || null,
        is_remote: mode.isRemote,
        deadline: values.deadline || null,
      },
      seedSkills: values.skills,
    });
  });

  return (
    <form onSubmit={submit} className="space-y-5">
      <section className="space-y-5 rounded-xl border border-rule bg-white p-6">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <label htmlFor="job-title" className="text-sm font-medium text-slate-700">
              Job title
            </label>
            <span className="tabular text-xs text-slate-400">
              {title.length}/{TITLE_MAX}
            </span>
          </div>
          <input
            id="job-title"
            maxLength={TITLE_MAX}
            placeholder="Backend Engineer — Payments"
            aria-invalid={Boolean(errors.title)}
            className="w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
            {...register("title", {
              required: "A title is required",
              maxLength: { value: TITLE_MAX, message: `Keep the title under ${TITLE_MAX} characters` },
            })}
          />
          {errors.title ? (
            <p role="alert" className="text-xs text-flagged">
              {errors.title.message}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <label htmlFor="job-description" className="text-sm font-medium text-slate-700">
              Description
            </label>
            <span
              className={cn(
                "tabular text-xs",
                descriptionLength < DESCRIPTION_MIN ? "text-slate-400" : "text-verified",
              )}
            >
              {descriptionLength}/{DESCRIPTION_MIN} min
            </span>
          </div>
          <textarea
            id="job-description"
            rows={10}
            placeholder={
              "What the role does, what the team owns, what you need from day one.\n\n**Bold** and - bullet lists are supported.\n\nThis text is what GroundTruth reads requirements out of — the more concrete it is, the better the extraction on the next screen."
            }
            aria-invalid={Boolean(errors.description)}
            aria-describedby="job-description-hint"
            className="w-full rounded border border-slate-300 bg-white px-4 py-2.5 font-sans text-sm leading-relaxed text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
            {...register("description", {
              required: "A description is required",
              minLength: {
                value: DESCRIPTION_MIN,
                message: `${DESCRIPTION_MIN} characters minimum — extraction has little to work with below that`,
              },
              onChange: (event) => setDescriptionLength(event.target.value.length),
            })}
          />
          <p id="job-description-hint" className="text-xs text-slate-500">
            Markdown-lite: <span className="font-semibold">**bold**</span> and <code>-</code> bullets.
          </p>
          {errors.description ? (
            <p role="alert" className="text-xs text-flagged">
              {errors.description.message}
            </p>
          ) : null}
        </div>

        <Controller
          control={control}
          name="skills"
          rules={{
            validate: (value) =>
              value.length >= MIN_SKILLS || `Add at least ${MIN_SKILLS} skills`,
          }}
          render={({ field, fieldState }) => (
            <TagInput
              label="Required skills"
              value={field.value}
              onChange={field.onChange}
              max={30}
              error={fieldState.error?.message}
              hint={`At least ${MIN_SKILLS}. These are a starting point — you confirm the final list on the next screen, alongside what GroundTruth reads out of your description.`}
            />
          )}
        />
      </section>

      <section className="space-y-5 rounded-xl border border-rule bg-white p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Job type" options={JOB_TYPE_OPTIONS} {...register("jobType")} />
          <Select
            label="Experience level"
            options={EXPERIENCE_BANDS.map((b) => ({ value: b.value, label: b.label }))}
            {...register("band")}
          />
        </div>

        {band.warning ? (
          <p
            role="status"
            className="flex items-start gap-2 rounded-lg border border-flagged/30 bg-flagged/10 px-3 py-2.5 text-xs leading-relaxed text-flagged"
          >
            <AlertTriangle size={14} className="mt-px shrink-0" aria-hidden="true" />
            {band.warning}
          </p>
        ) : null}

        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1.5 text-sm font-medium text-slate-700">Work mode</legend>
          <div className="flex flex-wrap gap-2">
            {WORK_MODES.map((mode) => (
              <label
                key={mode.value}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded border px-3.5 py-2 text-sm transition",
                  workMode.value === mode.value
                    ? "border-ink bg-ink/5 font-medium text-ink"
                    : "border-slate-300 text-slate-600 hover:border-ink/40",
                )}
              >
                <input
                  type="radio"
                  value={mode.value}
                  className="h-3.5 w-3.5 accent-gt-electric"
                  {...register("workMode")}
                />
                {mode.label}
              </label>
            ))}
          </div>
        </fieldset>

        {workMode.needsLocation ? (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="job-location" className="text-sm font-medium text-slate-700">
              Location
            </label>
            <input
              id="job-location"
              list="job-location-options"
              placeholder="Bangalore, India"
              autoComplete="off"
              aria-invalid={Boolean(errors.location)}
              className="w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
              {...register("location", {
                validate: (value, values) => {
                  const mode = WORK_MODES.find((m) => m.value === values.workMode);
                  if (!mode?.needsLocation) return true;
                  return value.trim().length > 0 || "A city is required for hybrid and onsite roles";
                },
              })}
            />
            <datalist id="job-location-options">
              {COMMON_LOCATIONS.map((city) => (
                <option key={city} value={city} />
              ))}
            </datalist>
            {errors.location ? (
              <p role="alert" className="text-xs text-flagged">
                {errors.location.message}
              </p>
            ) : (
              <p className="text-xs text-slate-500">
                City level. Candidates who have not stated a location are still matched — a missing
                answer is not a mismatch.
              </p>
            )}
          </div>
        ) : null}

        <Input
          type="date"
          label="Application deadline (optional)"
          className="max-w-xs"
          {...register("deadline")}
        />
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rule bg-panel px-5 py-4">
        <p className="text-xs leading-relaxed text-slate-500">
          This creates a draft. Nothing is visible to candidates until you review what GroundTruth
          extracts and publish it yourself.
        </p>
        <Button type="submit" isLoading={isSaving} className="bg-gt-electric hover:bg-gt-electric/90">
          Extract requirements
          <ArrowRight size={15} aria-hidden="true" />
        </Button>
      </div>
    </form>
  );
}
