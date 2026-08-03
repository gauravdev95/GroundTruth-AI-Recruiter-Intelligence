import { zodResolver } from "@hookform/resolvers/zod";
import { Github, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { Button, Input, Select, useToast } from "@/components";

import type { ProjectsSection, SectionStatus } from "../api/profileApi";
import { GithubRepoPicker } from "../components/GithubRepoPicker";
import { VerificationBadge } from "../components/SectionBadges";
import { SectionShell } from "../components/SectionShell";
import { TechnologiesField } from "../components/TechnologiesField";
import { SECTIONS } from "../constants";
import { useSaveProjects } from "../hooks/useProfileSection";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";
import { projectsSchema, type ProjectsForm as ProjectsFormValues } from "../schemas/profileSchemas";

const META = SECTIONS[2];
const MAX_PROJECTS = 3;

const KIND_OPTIONS = [
  { value: "repository", label: "Repository link" },
  { value: "described", label: "Described project" },
];

interface ProjectsFormProps {
  data: ProjectsSection;
  status: SectionStatus | undefined;
}

function toDefaults(data: ProjectsSection): ProjectsFormValues {
  return {
    projects: data.projects.map((project) => ({
      kind: project.kind,
      title: project.title,
      description: project.description ?? "",
      repo_url: project.repo_url ?? null,
      technologies: project.technologies,
    })),
  } as ProjectsFormValues;
}

export function ProjectsForm({ data, status }: ProjectsFormProps) {
  const save = useSaveProjects();
  const { showToast } = useToast();
  const [pickerOpen, setPickerOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<ProjectsFormValues>({
    resolver: zodResolver(projectsSchema),
    defaultValues: toDefaults(data),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "projects" });

  useEffect(() => {
    reset(toDefaults(data));
  }, [data, reset]);

  const onSubmit = handleSubmit((values) => {
    save.mutate(
      {
        projects: values.projects.map((project) => ({
          kind: project.kind,
          title: project.title,
          description: project.description?.trim() ? project.description : null,
          repo_url: project.repo_url ?? null,
          technologies: project.technologies,
        })),
      },
      { onSuccess: () => showToast("Projects saved.", "success") },
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
          No projects yet. Add up to {MAX_PROJECTS} repositories or described projects.
        </p>
      ) : null}

      {fields.map((field, index) => {
        const kind = watch(`projects.${index}.kind`);
        const existing = data.projects[index];

        return (
          <div key={field.id} className="rounded-xl border border-rule bg-panel p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className="font-mono text-xs text-slate-500">Project {index + 1}</span>
              <div className="flex items-center gap-2">
                {existing ? <VerificationBadge status={existing.verification_status} /> : null}
                {existing?.kind === "repository" && existing.verification_status === "verified" ? (
                  <Link
                    to={`/student/interview/${existing.id}`}
                    className="text-xs font-medium text-ink underline decoration-rule underline-offset-2 hover:decoration-ink"
                  >
                    Take AI interview
                  </Link>
                ) : null}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => remove(index)}
                  aria-label={`Remove project ${index + 1}`}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </Button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Select
                  label="Type"
                  options={KIND_OPTIONS}
                  error={errors.projects?.[index]?.kind?.message}
                  {...register(`projects.${index}.kind` as const)}
                />
                <Input
                  label="Title"
                  placeholder="Toy compiler"
                  error={errors.projects?.[index]?.title?.message}
                  {...register(`projects.${index}.title` as const)}
                />
              </div>

              {kind === "repository" ? (
                <Input
                  label="Repository URL"
                  placeholder="https://github.com/you/project"
                  error={errors.projects?.[index]?.repo_url?.message}
                  {...register(`projects.${index}.repo_url` as const)}
                />
              ) : null}

              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor={`project-description-${index}`}
                  className="text-sm font-medium text-slate-700"
                >
                  Description{kind === "described" ? "" : " (optional)"}
                </label>
                <textarea
                  id={`project-description-${index}`}
                  rows={3}
                  placeholder="What it does, what you built, what was hard."
                  className="w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
                  {...register(`projects.${index}.description` as const)}
                />
                {errors.projects?.[index]?.description?.message ? (
                  <p role="alert" className="text-xs text-red-500">
                    {errors.projects[index]?.description?.message}
                  </p>
                ) : null}
              </div>

              <Controller
                control={control}
                name={`projects.${index}.technologies` as const}
                render={({ field: techField }) => (
                  <TechnologiesField
                    value={techField.value ?? []}
                    onChange={techField.onChange}
                    error={errors.projects?.[index]?.technologies?.message}
                  />
                )}
              />
            </div>
          </div>
        );
      })}

      <div className="flex flex-wrap items-center gap-2">
        {fields.length < MAX_PROJECTS ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() =>
              append({ kind: "repository", title: "", description: "", repo_url: null, technologies: [] })
            }
          >
            <Plus size={14} aria-hidden="true" /> Add project
          </Button>
        ) : (
          <p className="text-xs text-slate-500">Maximum of {MAX_PROJECTS} projects reached.</p>
        )}
        <Button type="button" variant="secondary" size="sm" onClick={() => setPickerOpen(true)}>
          <Github size={14} aria-hidden="true" /> Import from GitHub
        </Button>
      </div>

      <GithubRepoPicker open={pickerOpen} onClose={() => setPickerOpen(false)} />

      <p className="rounded-xl border border-rule bg-panel px-3 py-2 text-xs text-slate-500">
        Repository links are queued for analysis on save. Described projects are recorded as your own
        account of the work and are not independently checked.
      </p>
    </SectionShell>
  );
}
