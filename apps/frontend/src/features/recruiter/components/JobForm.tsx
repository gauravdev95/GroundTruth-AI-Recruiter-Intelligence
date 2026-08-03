import { useForm } from "react-hook-form";

import { Button, Input, Select } from "@/components";

import type { ExperienceLevel, Job, JobCreatePayload, JobType } from "../api/jobsApi";

const JOB_TYPE_OPTIONS = [
  { value: "full_time", label: "Full-time" },
  { value: "part_time", label: "Part-time" },
  { value: "internship", label: "Internship" },
  { value: "contract", label: "Contract" },
];

const EXPERIENCE_LEVEL_OPTIONS = [
  { value: "entry", label: "Entry-level" },
  { value: "mid", label: "Mid-level" },
  { value: "senior", label: "Senior" },
];

interface JobFormProps {
  initial?: Job;
  isSaving: boolean;
  submitLabel: string;
  onSubmit: (payload: JobCreatePayload) => void;
}

function toDefaults(initial?: Job): JobCreatePayload {
  return {
    title: initial?.title ?? "",
    description: initial?.description ?? "",
    job_type: (initial?.job_type ?? "full_time") as JobType,
    experience_level: (initial?.experience_level ?? "entry") as ExperienceLevel,
    location: initial?.location ?? "",
    is_remote: initial?.is_remote ?? false,
    deadline: initial?.deadline ?? null,
  };
}

/** The recruiter-authored half of a job posting — title, description,
 * job type, experience level, location, deadline. Required skills are
 * deliberately not a field here: they only ever enter through LLM
 * extraction + the mandatory confirmation screen
 * (`RequirementsConfirmForm`), never typed free-hand at creation, so there
 * is exactly one path by which a skill reaches `job_requirements`. */
export function JobForm({ initial, isSaving, submitLabel, onSubmit }: JobFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<JobCreatePayload>({ defaultValues: toDefaults(initial) });

  const isRemote = watch("is_remote");

  return (
    <form
      className="space-y-4 rounded-2xl border border-rule bg-white p-6"
      onSubmit={handleSubmit((values) =>
        onSubmit({
          ...values,
          location: values.is_remote ? null : values.location || null,
          deadline: values.deadline || null,
        }),
      )}
    >
      <Input
        label="Job title"
        placeholder="Backend Engineer Intern"
        error={errors.title?.message}
        {...register("title", { required: "Title is required", minLength: 3, maxLength: 200 })}
      />

      <div className="flex flex-col gap-1.5">
        <label htmlFor="job-description" className="text-sm font-medium text-slate-700">
          Description
        </label>
        <textarea
          id="job-description"
          rows={8}
          placeholder="Describe the role, responsibilities, and what you're looking for. GroundTruth will mine required skills from this text."
          className="w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
          {...register("description", { required: "Description is required", minLength: 20 })}
        />
        {errors.description?.message ? (
          <p role="alert" className="text-xs text-red-500">
            {errors.description.message}
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Select label="Job type" options={JOB_TYPE_OPTIONS} {...register("job_type")} />
        <Select label="Experience level" options={EXPERIENCE_LEVEL_OPTIONS} {...register("experience_level")} />
      </div>

      <label className="flex cursor-pointer items-center gap-2.5 text-sm text-slate-600">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300 accent-verified"
          {...register("is_remote")}
        />
        This role is fully remote
      </label>

      {!isRemote ? (
        <Input label="Location" placeholder="Bangalore, India" {...register("location")} />
      ) : null}

      <Input type="date" label="Application deadline (optional)" {...register("deadline")} />

      <div className="flex justify-end">
        <Button type="submit" isLoading={isSaving} disabled={isSaving}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
