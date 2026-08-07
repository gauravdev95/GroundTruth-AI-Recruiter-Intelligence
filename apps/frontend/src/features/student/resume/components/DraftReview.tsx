import { useMemo, useState } from "react";

import { Button, useToast } from "@/components";

import type { CodingPlatformType } from "../../api/profileApi";
import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import {
  basicInfoSchema,
  certificatesSchema,
  experiencesSchema,
  projectsSchema,
  technicalSchema,
} from "../../schemas/profileSchemas";
import type { ConfirmDraftPayload, ResumeDraftDetail } from "../api/resumeApi";
import { useConfirmDraft, useDiscardDraft } from "../hooks/useResumeImport";
import { BasicReview, type BasicFieldName, type BasicFieldsState } from "./BasicReview";
import { ListReview, type ListItemState } from "./ListReview";
import { TechnicalReview, type TechnicalFieldsState } from "./TechnicalReview";

const BASIC_FIELDS: BasicFieldName[] = [
  // Required by the section since signup stopped collecting it. Omitting it
  // here made every basic-section confirm fail validation against a field the
  // screen never rendered.
  "full_name",
  "headline",
  "college",
  "degree",
  "branch",
  "graduation_year",
  "location",
  "target_role",
];

const PLATFORMS: CodingPlatformType[] = ["leetcode", "codeforces", "hackerrank", "codechef"];

interface DraftReviewProps {
  detail: ResumeDraftDetail;
  onDone: () => void;
}

/**
 * Field-by-field review of an extraction draft.
 *
 * Nothing here writes to the profile. The student toggles each field and each
 * list entry, edits anything the model got wrong, and only the accepted subset
 * is sent to the confirm endpoint — which is the sole path from a draft into a
 * live section.
 *
 * The built payload is validated with the **same zod schemas the profile
 * builder's forms use** before it is sent, so a bad import surfaces inline
 * rather than as a 422 from the server.
 */
export function DraftReview({ detail, onDone }: DraftReviewProps) {
  const { suggestions, draft } = detail;
  const confirm = useConfirmDraft();
  const discard = useDiscardDraft();
  const { showToast } = useToast();

  const [basic, setBasic] = useState<BasicFieldsState>(() => {
    const initial = {} as BasicFieldsState;
    for (const name of BASIC_FIELDS) {
      const raw = (suggestions.basic as Record<string, unknown>)[name];
      const fromResume = raw !== undefined && raw !== null && raw !== "";
      initial[name] = {
        included: fromResume,
        value: fromResume ? String(raw) : "",
        fromResume,
      };
    }
    return initial;
  });

  const [technical, setTechnical] = useState<TechnicalFieldsState>(() => {
    const github = suggestions.technical.github_username ?? "";
    const suggested = new Map(
      (suggestions.technical.coding_profiles ?? []).map((p) => [p.platform, p.handle]),
    );
    return {
      github: { included: Boolean(github), value: github, fromResume: Boolean(github) },
      platforms: PLATFORMS.reduce(
        (acc, platform) => {
          const handle = suggested.get(platform) ?? "";
          acc[platform] = {
            included: Boolean(handle),
            value: handle,
            fromResume: Boolean(handle),
          };
          return acc;
        },
        {} as TechnicalFieldsState["platforms"],
      ),
    };
  });

  const [projects, setProjects] = useState<ListItemState<Record<string, unknown>>[]>(() =>
    suggestions.projects.map((value) => ({ included: true, value: { ...value } })),
  );
  const [certificates, setCertificates] = useState<ListItemState<Record<string, unknown>>[]>(() =>
    suggestions.certificates.map((value) => ({ included: true, value: { ...value } })),
  );
  const [experience, setExperience] = useState<ListItemState<Record<string, unknown>>[]>(() =>
    suggestions.experience.map((value) => ({ included: true, value: { ...value } })),
  );

  const [sectionErrors, setSectionErrors] = useState<Record<string, string>>({});
  const [basicErrors, setBasicErrors] = useState<Partial<Record<BasicFieldName, string>>>({});

  const includedCount = useMemo(() => {
    const basicOn = BASIC_FIELDS.some((name) => basic[name].included);
    const technicalOn =
      technical.github.included || PLATFORMS.some((p) => technical.platforms[p].included);
    return (
      Number(basicOn) +
      Number(technicalOn) +
      Number(projects.some((p) => p.included)) +
      Number(certificates.some((c) => c.included)) +
      Number(experience.some((e) => e.included))
    );
  }, [basic, technical, projects, certificates, experience]);

  /** Build the confirm payload from accepted fields, validating each section. */
  function buildPayload(): ConfirmDraftPayload | null {
    const payload: ConfirmDraftPayload = {};
    const nextSectionErrors: Record<string, string> = {};
    const nextBasicErrors: Partial<Record<BasicFieldName, string>> = {};

    // Section 1 is all-or-nothing: every field is required, so a partially
    // toggled section can't be submitted.
    const anyBasic = BASIC_FIELDS.some((name) => basic[name].included);
    if (anyBasic) {
      const candidate: Record<string, unknown> = Object.fromEntries(
        BASIC_FIELDS.map((name) => [name, basic[name].included ? basic[name].value : ""]),
      );
      // The section takes one to three roles; this screen collects one.
      //
      // A resume states no target role at all — it is forward-looking, and
      // `resume/confirm.py` reports it as unmapped for exactly that reason — so
      // every value here is one the student just picked from a dropdown.
      // Rendering a three-way chip picker to capture a field the parser never
      // supplies would add a decision to a screen whose whole job is confirming
      // what was extracted. They set the other two in the profile editor, where
      // the full control lives.
      const primaryRole = candidate.target_role;
      delete candidate.target_role;
      candidate.target_roles = primaryRole ? [primaryRole] : [];

      const parsed = basicInfoSchema.safeParse(candidate);
      if (parsed.success) {
        payload.basic = parsed.data;
      } else {
        for (const issue of parsed.error.issues) {
          // `target_roles` is the schema's name for what this screen calls
          // `target_role`; mapping it back is what puts the error under the
          // dropdown the student can actually change.
          const field = (issue.path[0] === "target_roles" ? "target_role" : issue.path[0]) as BasicFieldName;
          if (field) nextBasicErrors[field] = issue.message;
        }
        nextSectionErrors.basic =
          "Basic Information needs every field. Fill or untick the highlighted ones.";
      }
    }

    const codingProfiles = PLATFORMS.filter((p) => technical.platforms[p].included).map((p) => ({
      platform: p,
      handle: technical.platforms[p].value,
    }));
    if (technical.github.included || codingProfiles.length > 0) {
      const parsed = technicalSchema.safeParse({
        github_username: technical.github.value,
        coding_profiles: codingProfiles,
      });
      if (parsed.success) {
        payload.technical = parsed.data;
      } else {
        nextSectionErrors.technical =
          parsed.error.issues[0]?.message ??
          "Technical Verification needs a GitHub username and one coding profile.";
      }
    }

    const acceptedProjects = projects.filter((p) => p.included).map((p) => p.value);
    if (acceptedProjects.length > 0) {
      const parsed = projectsSchema.safeParse({ projects: acceptedProjects });
      if (parsed.success) payload.projects = parsed.data;
      else nextSectionErrors.projects = parsed.error.issues[0]?.message ?? "Check your projects.";
    }

    const acceptedCerts = certificates.filter((c) => c.included).map((c) => c.value);
    if (acceptedCerts.length > 0) {
      const parsed = certificatesSchema.safeParse({ certificates: acceptedCerts });
      if (parsed.success) payload.certificates = parsed.data;
      else
        nextSectionErrors.certificates =
          parsed.error.issues[0]?.message ?? "Check your certificates.";
    }

    const acceptedExperience = experience.filter((e) => e.included).map((e) => e.value);
    if (acceptedExperience.length > 0) {
      const parsed = experiencesSchema.safeParse({ experiences: acceptedExperience });
      if (parsed.success) payload.experience = parsed.data;
      else
        nextSectionErrors.experience = parsed.error.issues[0]?.message ?? "Check your experience.";
    }

    setSectionErrors(nextSectionErrors);
    setBasicErrors(nextBasicErrors);
    return Object.keys(nextSectionErrors).length > 0 ? null : payload;
  }

  function handleConfirm() {
    const payload = buildPayload();
    if (payload === null) return;
    if (Object.keys(payload).length === 0) {
      setSectionErrors({ form: "Select at least one thing to import." });
      return;
    }

    confirm.mutate(
      { draftId: draft.id, payload },
      {
        onSuccess: (result) => {
          showToast(
            `Imported. Profile strength is now ${result.completeness.profile_strength}/100.`,
            "success",
          );
          onDone();
        },
      },
    );
  }

  const sectionShell = (title: string, description: string, key: string, body: React.ReactNode) => (
    <section className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
      <header className="mb-4">
        <h3 className="font-display text-base font-semibold text-[var(--ink)]">{title}</h3>
        <p className="mt-0.5 text-sm text-[var(--slate)]">{description}</p>
      </header>
      {sectionErrors[key] ? (
        <p
          role="alert"
          className="mb-3 rounded border border-[var(--failed)]/30 bg-[var(--failed)]/10 px-3 py-2 text-sm text-[var(--failed)]"
        >
          {sectionErrors[key]}
        </p>
      ) : null}
      {body}
    </section>
  );

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-[var(--flagged)]/30 bg-[var(--flagged)]/10 p-4 text-sm">
        <p className="font-medium text-[var(--ink)]">Nothing here is saved yet.</p>
        <p className="mt-0.5 text-[var(--slate)]">
          This was read from your resume by {draft.provider} ({draft.model}). Check each field —
          untick anything that&apos;s wrong, and correct what you keep. Only what you confirm is
          written to your profile.
        </p>
        {suggestions.unmapped.length > 0 ? (
          <ul className="mt-2 list-inside list-disc space-y-0.5 text-[var(--slate)]">
            {suggestions.unmapped.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </div>

      {confirm.isError ? (
        <p
          role="alert"
          className="rounded border border-[var(--failed)]/30 bg-[var(--failed)]/10 px-3 py-2 text-sm text-[var(--failed)]"
        >
          {getProfileErrorMessage(confirm.error)}
        </p>
      ) : null}
      {sectionErrors.form ? (
        <p role="alert" className="text-sm text-[var(--failed)]">
          {sectionErrors.form}
        </p>
      ) : null}

      {sectionShell(
        "Basic Information",
        "Required section — every field must be filled to import it.",
        "basic",
        <BasicReview
          fields={basic}
          errors={basicErrors}
          onChange={(name, next) =>
            setBasic((current) => ({ ...current, [name]: { ...current[name], ...next } }))
          }
        />,
      )}

      {sectionShell(
        "Technical Verification",
        "Needs a GitHub username and at least one coding profile.",
        "technical",
        <TechnicalReview
          fields={technical}
          errors={{ github: undefined, platforms: undefined }}
          onGithubChange={(next) =>
            setTechnical((current) => ({ ...current, github: { ...current.github, ...next } }))
          }
          onPlatformChange={(platform, next) =>
            setTechnical((current) => ({
              ...current,
              platforms: {
                ...current.platforms,
                [platform]: { ...current.platforms[platform], ...next },
              },
            }))
          }
        />,
      )}

      {sectionShell(
        "Projects",
        "Up to three repositories or described projects.",
        "projects",
        <ListReview
          kind="projects"
          items={projects}
          emptyMessage="No projects were found in your resume."
          onToggle={(index, included) =>
            setProjects((current) =>
              current.map((item, i) => (i === index ? { ...item, included } : item)),
            )
          }
          onChange={(index, next) =>
            setProjects((current) =>
              current.map((item, i) =>
                i === index ? { ...item, value: { ...item.value, ...next } } : item,
              ),
            )
          }
        />,
      )}

      {sectionShell(
        "Certificates",
        "Credentials found in your resume.",
        "certificates",
        <ListReview
          kind="certificates"
          items={certificates}
          emptyMessage="No certificates were found in your resume."
          onToggle={(index, included) =>
            setCertificates((current) =>
              current.map((item, i) => (i === index ? { ...item, included } : item)),
            )
          }
          onChange={(index, next) =>
            setCertificates((current) =>
              current.map((item, i) =>
                i === index ? { ...item, value: { ...item.value, ...next } } : item,
              ),
            )
          }
        />,
      )}

      {sectionShell(
        "Experience",
        "Internships, freelance and part-time work.",
        "experience",
        <ListReview
          kind="experience"
          items={experience}
          emptyMessage="No experience entries were found in your resume."
          onToggle={(index, included) =>
            setExperience((current) =>
              current.map((item, i) => (i === index ? { ...item, included } : item)),
            )
          }
          onChange={(index, next) =>
            setExperience((current) =>
              current.map((item, i) =>
                i === index ? { ...item, value: { ...item.value, ...next } } : item,
              ),
            )
          }
        />,
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-4">
        <p className="text-sm text-[var(--slate)]">
          {includedCount === 0
            ? "Nothing selected yet."
            : `${includedCount} section${includedCount === 1 ? "" : "s"} will be imported.`}
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() =>
              discard.mutate(draft.id, {
                onSuccess: () => {
                  showToast("Draft discarded. Nothing was saved.", "info");
                  onDone();
                },
              })
            }
            disabled={discard.isPending || confirm.isPending}
          >
            Discard
          </Button>
          <Button
            type="button"
            onClick={handleConfirm}
            isLoading={confirm.isPending}
            disabled={confirm.isPending || includedCount === 0}
          >
            {confirm.isPending ? "Importing..." : "Import selected"}
          </Button>
        </div>
      </div>
    </div>
  );
}
