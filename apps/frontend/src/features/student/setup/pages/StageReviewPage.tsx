import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Check, Circle, Pencil, Plus } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button, ErrorState, Skeleton, useToast } from "@/components";
import { queryKeys } from "@/lib/queryKeys";

import type { SectionKey } from "../../api/profileApi";
import {
  useBasicSection,
  useCertificatesSection,
  useExperiencesSection,
  useProjectsSection,
  useTechnicalSection,
} from "../../hooks/useProfileSection";
import { TARGET_ROLE_OPTIONS } from "../../constants";
import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { setupApi } from "../api/setupApi";
import { useSetupState } from "../hooks/useSetupState";
import { useStageNav } from "../hooks/useStageNav";
import { stageBySectionKey, stagePath } from "../lib/stages";

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 py-1.5">
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      {/* An unfilled optional field says so rather than rendering blank — a gap
          in a summary reads as data the flow lost. */}
      <dd className="text-sm text-slate-700">
        {value?.trim() ? value : <span className="text-slate-400">Not provided</span>}
      </dd>
    </div>
  );
}

/**
 * One section's summary.
 *
 * A skipped optional section renders as an explicit "Skipped" row with an
 * "Add" action rather than being omitted. Omitting it would leave the student
 * unable to tell "I chose not to fill this" from "the flow never asked me",
 * and this is the last screen where they can still act on the difference.
 */
function Panel({
  title,
  section,
  filled,
  children,
}: {
  title: string;
  section: SectionKey;
  filled: boolean;
  children: ReactNode;
}) {
  const stage = stageBySectionKey(section);
  const to = stage ? stagePath(stage) : ".";

  return (
    <section className="rounded-2xl border border-rule bg-white p-5">
      <header className="mb-3 flex items-center justify-between gap-3 border-b border-rule pb-3">
        <h3 className="flex items-center gap-2 font-display text-sm font-semibold text-ink">
          {filled ? (
            <Check size={15} className="text-verified" aria-hidden="true" />
          ) : (
            <Circle size={13} className="text-slate-300" aria-hidden="true" />
          )}
          {title}
          {!filled ? <span className="font-normal text-slate-400">— Skipped</span> : null}
        </h3>
        {/* A real link, not a button with an onClick: "Edit" navigates to
            another stage, so it must be middle-clickable and copyable like
            every other navigation in the flow. `Button` has no `asChild`, so
            this borrows its ghost styling rather than nesting the two. */}
        <Link
          to={to}
          className="inline-flex shrink-0 items-center rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-panel hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          {filled ? (
            <>
              <Pencil size={13} aria-hidden="true" className="mr-1.5" />
              Edit
            </>
          ) : (
            <>
              <Plus size={13} aria-hidden="true" className="mr-1.5" />
              Add
            </>
          )}
        </Link>
      </header>
      {children}
    </section>
  );
}

/**
 * Stage 7 — the whole profile, the consent, then Submit.
 *
 * Reads the section endpoints rather than a bespoke "review" endpoint: the
 * summary must show exactly what was saved, and a second server-side assembly
 * of the same data is a second thing that can disagree with it.
 *
 * **Consent is a hard gate on the button and is sent with the submission.**
 * The server records `onboarding_consent_at` in the same transaction that
 * stamps `onboarding_submitted_at`, so there is no ordering in which a profile
 * is submitted — and therefore analysed — under a consent record that failed
 * to write. Ticking the box is a local state, not a saved one: an unsubmitted
 * tick means nothing and must not be persisted as though it did.
 *
 * Submitting is the only action in the flow that opens the dashboard. Every
 * background check it starts is deliberately *not* waited on — the button
 * navigates as soon as the submission is recorded, and results arrive by email.
 */
export function StageReviewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const { goBack } = useStageNav();

  const [consent, setConsent] = useState(false);

  const setupState = useSetupState();
  const basic = useBasicSection();
  const technical = useTechnicalSection();
  const projects = useProjectsSection();
  const certificates = useCertificatesSection();
  const experiences = useExperiencesSection();

  const submit = useMutation({
    mutationFn: () => setupApi.submit(consent),
    onSuccess: (result) => {
      // Seeded, not invalidated: the gate on `/student` reads this exact
      // value, and navigating while a refetch is still in flight would bounce
      // the student straight back into setup.
      queryClient.setQueryData(queryKeys.studentProfile.completeness(), result.completeness);
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentProfile.setupState() });
      showToast(
        result.queued_verifications > 0
          ? `Profile submitted. ${result.queued_verifications} checks are running in the background.`
          : "Profile submitted.",
        "success",
      );
      navigate("/student/dashboard", { replace: true });
    },
    onError: (error) => showToast(getProfileErrorMessage(error), "error"),
  });

  const isLoading =
    setupState.isPending ||
    basic.isPending ||
    technical.isPending ||
    projects.isPending ||
    certificates.isPending ||
    experiences.isPending;

  if (isLoading) return <Skeleton className="h-96 w-full rounded-2xl" />;

  if (basic.isError || technical.isError || setupState.isError) {
    return (
      <ErrorState
        title="Could not load your profile"
        description="Something went wrong fetching what you saved. Refresh to try again."
      />
    );
  }

  const state = setupState.data!;
  const basicData = basic.data!.data;
  const technicalData = technical.data!.data;
  const projectList = projects.data?.data.projects ?? [];
  const certificateList = certificates.data?.data.certificates ?? [];
  const experienceList = experiences.data?.data.experiences ?? [];

  const roleLabels = (basicData.target_roles ?? [])
    .map((role) => TARGET_ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role)
    .join(", ");

  return (
    <div className="space-y-4">
      <header className="rounded-2xl border border-violet-100 bg-white p-5">
        <h1 className="font-display text-lg font-semibold text-ink">Review &amp; submit</h1>
        <p className="mt-1 text-sm text-slate-500">
          This is everything on your profile. Edit any section, then submit — verification starts in
          the background and you&apos;ll be emailed when it finishes.
        </p>
      </header>

      {!state.can_submit ? (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          <AlertTriangle size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
          <span>Still needed before you can submit: {state.blocking.join(", ")}.</span>
        </p>
      ) : null}

      <Panel title="Basic information" section="basic" filled>
        <dl className="divide-y divide-rule">
          <Row label="Name" value={basicData.full_name} />
          <Row label="Headline" value={basicData.headline} />
          <Row label="College" value={basicData.college} />
          <Row label="Degree" value={basicData.degree} />
          <Row label="Branch" value={basicData.branch} />
          <Row label="Graduation" value={basicData.graduation_year?.toString()} />
          <Row label="Location" value={basicData.location} />
          {/* All of them, not just the primary — the student picked up to
              three and the summary has to show what they chose. */}
          <Row label="Target roles" value={roleLabels} />
        </dl>
      </Panel>

      <Panel title="GitHub" section="github" filled={technicalData.github_account !== null}>
        <dl className="divide-y divide-rule">
          <Row label="Connected as" value={technicalData.github_account?.github_username} />
          <Row
            label="Projects linked"
            value={`${projectList.length} of 3`}
          />
        </dl>
      </Panel>

      <Panel title={`Projects (${projectList.length})`} section="projects" filled={projectList.length > 0}>
        {projectList.length === 0 ? (
          <p className="text-sm text-slate-400">None linked.</p>
        ) : (
          <ul className="divide-y divide-rule">
            {projectList.map((project) => (
              <li key={project.id} className="py-2">
                <p className="text-sm font-medium text-slate-800">
                  {project.title}
                  {project.is_primary ? (
                    <span className="ml-2 rounded-full bg-violet-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                      Main
                    </span>
                  ) : null}
                </p>
                {project.description ? (
                  <p className="mt-0.5 text-xs text-slate-600">&ldquo;{project.description}&rdquo;</p>
                ) : null}
                {project.repo_url ? (
                  <p className="truncate font-mono text-xs text-slate-500">{project.repo_url}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel
        title="Coding profile"
        section="coding"
        filled={technicalData.coding_profiles.length > 0}
      >
        {technicalData.coding_profiles.length === 0 ? (
          <p className="text-sm text-slate-400">None added.</p>
        ) : (
          <dl className="divide-y divide-rule">
            {technicalData.coding_profiles.map((account) => (
              <Row
                key={account.id}
                label={account.custom_platform_name ?? account.platform}
                value={account.handle}
              />
            ))}
          </dl>
        )}
      </Panel>

      <Panel
        title={`Certificates (${certificateList.length})`}
        section="certificates"
        filled={certificateList.length > 0}
      >
        {certificateList.length === 0 ? (
          <p className="text-sm text-slate-400">None added.</p>
        ) : (
          <ul className="divide-y divide-rule">
            {certificateList.map((certificate) => (
              <li key={certificate.id} className="py-2">
                <p className="text-sm font-medium text-slate-800">{certificate.title}</p>
                <p className="text-xs text-slate-500">
                  {certificate.issuer}
                  {certificate.file_name ? ` · ${certificate.file_name}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel
        title={`Experience (${experienceList.length})`}
        section="experience"
        filled={experienceList.length > 0}
      >
        {experienceList.length === 0 ? (
          <p className="text-sm text-slate-400">None added.</p>
        ) : (
          <ul className="divide-y divide-rule">
            {experienceList.map((experience) => (
              <li key={experience.id} className="py-2">
                <p className="text-sm font-medium text-slate-800">
                  {experience.title} · {experience.company_name}
                </p>
                <p className="text-xs text-slate-500">
                  {experience.start_date} — {experience.end_date ?? "Present"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <section className="rounded-2xl border border-rule bg-white p-5">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            disabled={state.is_submitted || submit.isPending}
            className="mt-0.5 size-4 shrink-0 rounded border-slate-300 accent-ink"
          />
          <span className="text-sm leading-relaxed text-slate-700">
            I consent to GroundTruth analysing my linked repositories and generating interview
            questions based on this data, as described in the{" "}
            <a
              href="/legal/privacy"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-ink"
            >
              Privacy Policy
            </a>
            .
          </span>
        </label>
      </section>

      <footer className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rule bg-white p-5">
        <Button type="button" variant="secondary" onClick={goBack} disabled={submit.isPending}>
          <ArrowLeft size={16} aria-hidden="true" className="mr-1.5" />
          Previous
        </Button>
        <Button
          type="button"
          onClick={() => submit.mutate()}
          isLoading={submit.isPending}
          // Consent is part of the gate, alongside the server's own
          // `can_submit`. The server refuses a submission without it too — this
          // is the courtesy, not the enforcement.
          disabled={!state.can_submit || !consent || submit.isPending || state.is_submitted}
        >
          {state.is_submitted ? "Already submitted" : "Submit profile"}
        </Button>
      </footer>
    </div>
  );
}
