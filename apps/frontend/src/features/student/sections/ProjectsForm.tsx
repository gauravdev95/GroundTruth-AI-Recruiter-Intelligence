import { zodResolver } from "@hookform/resolvers/zod";
import { Github, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { Button, Input, Select, useToast } from "@/components";

import type { ProjectsSection, SectionStatus } from "../api/profileApi";
import { GithubRepoPicker } from "../components/GithubRepoPicker";
import { VerificationBadge } from "../components/SectionBadges";
import { SectionShell, type SectionNav } from "../components/SectionShell";
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

/**
 * Read-only view of the technologies verification detected in a repository's
 * dependency manifests.
 *
 * This replaced an editable tag input. The whole product claim is that a skill
 * on a profile was *found*, not typed — an editable field here produced
 * self-declared technologies that rendered identically to detected ones, so
 * neither the candidate nor a recruiter could tell them apart.
 *
 * The empty state says *why* it is empty rather than hiding, because a blank
 * space next to a repository that has not been analysed yet reads as a bug.
 */
function DetectedTechnologies({ technologies }: { technologies: string[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-slate-700">Detected technologies</span>
      {technologies.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5">
          {technologies.map((tech) => (
            <li
              key={tech}
              className="rounded-full border border-verified/30 bg-verified/10 px-2.5 py-1 text-xs font-medium text-slate-700"
            >
              {tech}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-500">
          Nothing detected yet — these are read from the repository&apos;s dependency files when
          verification runs, not entered by hand.
        </p>
      )}
    </div>
  );
}

interface ProjectsFormProps {
  data: ProjectsSection;
  status: SectionStatus | undefined;
  nav?: SectionNav;
}

function toDefaults(data: ProjectsSection): ProjectsFormValues {
  return {
    projects: data.projects.map((project) => ({
      kind: project.kind,
      title: project.title,
      description: project.description ?? "",
      repo_url: project.repo_url ?? null,
      live_demo_url: project.live_demo_url ?? null,
      is_primary: project.is_primary,
      claimed_technologies: project.claimed_technologies ?? [],
    })),
  } as ProjectsFormValues;
}

export function ProjectsForm({ data, status, nav }: ProjectsFormProps) {
  const save = useSaveProjects();
  const { showToast } = useToast();
  const [pickerOpen, setPickerOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ProjectsFormValues>({
    resolver: zodResolver(projectsSchema),
    defaultValues: toDefaults(data),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "projects" });

  useEffect(() => {
    reset(toDefaults(data));
  }, [data, reset]);

  /** Nominating one project un-nominates the rest.
   *
   * Enforced here rather than by a native radio `name` group, because
   * react-hook-form registers each row independently and a shared name would
   * leave the *form state* holding two `true`s even while the DOM showed one
   * — which is exactly the shape the server rejects. */
  const setPrimary = (index: number) => {
    fields.forEach((_field, i) => {
      setValue(`projects.${i}.is_primary` as const, i === index, { shouldDirty: true });
    });
  };

  const onSubmit = handleSubmit((values) => {
    save.mutate(
      {
        projects: values.projects.map((project) => ({
          kind: project.kind,
          title: project.title,
          description: project.description?.trim() ? project.description : null,
          repo_url: project.repo_url ?? null,
          live_demo_url: project.live_demo_url ?? null,
          is_primary: project.is_primary,
          claimed_technologies: project.claimed_technologies,
        })),
      },
      {
        onSuccess: () => {
          showToast("Projects saved.", "success");
          nav?.onSaved();
        },
      },
    );
  });

  return (
    <SectionShell
      meta={META}
      status={status}
      onSubmit={onSubmit}
      isSaving={save.isPending}
      errorMessage={save.isError ? getProfileErrorMessage(save.error) : null}
      nav={nav}
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

              <div className="grid gap-4 sm:grid-cols-2">
                {kind === "repository" ? (
                  <Input
                    label="Repository URL"
                    placeholder="https://github.com/you/project"
                    error={errors.projects?.[index]?.repo_url?.message}
                    {...register(`projects.${index}.repo_url` as const)}
                  />
                ) : null}
                <Input
                  label="Live demo (optional)"
                  placeholder="https://your-project.vercel.app"
                  error={errors.projects?.[index]?.live_demo_url?.message}
                  {...register(`projects.${index}.live_demo_url` as const)}
                />
              </div>

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
                name={`projects.${index}.claimed_technologies` as const}
                render={({ field: techField }) => (
                  <TechnologiesField
                    label="Technologies"
                    value={techField.value ?? []}
                    onChange={techField.onChange}
                    error={errors.projects?.[index]?.claimed_technologies?.message}
                  />
                )}
              />
              <p className="-mt-3 text-xs text-slate-500">
                What you built it with. Recruiters see this as your description of the project — the
                skills on your profile come from the detected list below instead.
              </p>

              <DetectedTechnologies technologies={data.projects[index]?.technologies ?? []} />

              <label className="flex items-start gap-2.5 rounded-lg border border-rule bg-white px-3 py-2.5">
                <input
                  type="radio"
                  name="primary-project"
                  className="mt-0.5 size-4 accent-violet-600"
                  checked={watch(`projects.${index}.is_primary`) === true}
                  onChange={() => setPrimary(index)}
                />
                <span className="text-sm text-slate-700">
                  <span className="font-medium">Main project</span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    The one that best matches the roles you want. Recruiters see it first.
                  </span>
                </span>
              </label>
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
              append({
                kind: "repository",
                title: "",
                description: "",
                repo_url: null,
                live_demo_url: null,
                is_primary: fields.length === 0,
                claimed_technologies: [],
              })
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
