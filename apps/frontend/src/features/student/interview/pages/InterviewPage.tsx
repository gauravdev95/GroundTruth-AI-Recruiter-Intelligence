import { isAxiosError } from "axios";
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  Clock,
  ExternalLink,
  GitBranch,
  Loader2,
  MessageSquare,
  Mic,
  ShieldCheck,
  Video,
} from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge, Button, Card, ErrorState, Skeleton } from "@/components";
import { Reveal, Stagger, Surface } from "@/design";

import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { useProjectsSection } from "../../hooks/useProfileSection";
import { VerificationBadge } from "../../components/SectionBadges";
import type { Project } from "../../api/profileApi";
import type { InterviewSummary } from "../api/interviewApi";
import { EvidenceReportView } from "../components/EvidenceReportView";
import {
  useEvidenceReport,
  useInterviewState,
  useLatestInterview,
  useStartInterview,
} from "../hooks/useInterview";

/**
 * The interview lobby and, afterwards, the report.
 *
 * **The conversation itself is not here any more.** It moved to
 * `room/pages/InterviewRoomPage.tsx`, which renders outside the dashboard
 * shell — see the route comment in `features/student/routes.tsx`. This page
 * keeps the two halves that genuinely want a sidebar around them: the
 * explanation before an interview and the evidence report after one.
 *
 * `:projectId` (not `:interviewId`) — a repository has at most one
 * non-failed interview attempt ever, so the project is the stable thing to
 * link to from `ProjectsForm`; the interview itself is resolved underneath.
 *
 * The project card reads the same projects section the profile builder
 * writes, so the repository, its verification state and its detected
 * technologies are the server's own — never re-typed here. A repository
 * whose verification has not reached `verified` keeps the server's block:
 * the start button is disabled with the reason on screen, and the 409 the
 * start endpoint returns is still surfaced if it is ever reached.
 */
export function InterviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const latest = useLatestInterview(projectId ?? "");
  const start = useStartInterview();
  const projects = useProjectsSection();

  const notStartedYet = latest.isError && isAxiosError(latest.error) && latest.error.response?.status === 404;
  const startFailed =
    latest.isError && !(isAxiosError(latest.error) && latest.error.response?.status === 404);

  const interviewId =
    latest.data?.id ?? (start.data && start.data.project_id === projectId ? start.data.id : null);
  const query = useInterviewState(interviewId);
  const status = query.data?.interview.status;
  const report = useEvidenceReport(interviewId ?? "", status === "completed");

  const roomPath = `/student/interview/${projectId}/room`;

  // Starting an interview *is* joining it. The room's own device check is the
  // pause between the two, so there is no reason to make the candidate press a
  // second button here — and a lobby that sat between "Start" and the room
  // would be one more screen between them and the thing they came for.
  //
  // No socket is opened on this page. It used to hold the live conversation;
  // now the room does, and two live sessions against one interview would race
  // for the `FOR UPDATE NOWAIT` lock in `service.advance`.
  useEffect(() => {
    if (start.isSuccess && start.data?.project_id === projectId) {
      navigate(roomPath, { replace: true });
    }
  }, [start.isSuccess, start.data?.project_id, projectId, navigate, roomPath]);

  // A repository-verification-required 409 is the one failure worth its own
  // message; everything else falls back to the generic one.
  const startErrorMessage = start.isError
    ? getProfileErrorMessage(start.error, "Could not start the interview.")
    : null;

  if (!projectId) return null;

  const projectList = projects.data?.data.projects ?? [];
  const project = projectList.find((item) => item.id === projectId) ?? null;
  const otherVerified = projectList.filter(
    (item) => item.id !== projectId && item.verification_status === "verified",
  );
  // Only block on a *known* state. If the projects section has not loaded, or
  // this project is not in it, the start endpoint remains the authority and
  // its 409 is surfaced below — the page must not invent a block it cannot
  // prove.
  const knownUnverified = project !== null && project.verification_status !== "verified";

  const backLink = (
    <Link
      to="/student/profile"
      className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] transition-colors hover:text-[var(--ink)]"
    >
      <ArrowLeft size={14} aria-hidden="true" /> Back to profile
    </Link>
  );

  if (latest.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-16 w-full max-w-md" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (startFailed) {
    return (
      <div className="space-y-4">
        {backLink}
        <ErrorState
          title="Could not load this interview"
          description={getProfileErrorMessage(latest.error, "Something went wrong.")}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Reveal trigger="mount">
        <header>
          {backLink}
          <p className="mt-4 text-xs font-semibold uppercase tracking-[var(--tracking-overline)] text-[var(--muted)]">
            AI interview
          </p>
          <h1 className="mt-1 font-display text-[var(--fs-h1)] font-semibold leading-[var(--lh-h1)] text-[var(--ink)]">
            Code-grounded AI interview
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--slate)]">
            A ten-minute spoken conversation about your repository with an interviewer that has
            already read it. Every question traces back to something GroundTruth actually found in
            your code — nothing generic.
          </p>
        </header>
      </Reveal>

      {project ? <ProjectCard project={project} /> : null}

      {/* No attempt exists yet, or the most recent one failed — either way, offer
          to start (a fresh `start` call is allowed after `failed`; see
          `interview/service.py::_BLOCKING_STATUSES`). Once `start` succeeds it
          overwrites this same cache entry with the new `pending` interview, so
          this branch naturally stops matching on the next render. */}
      {notStartedYet || latest.data?.status === "failed" ? (
        <Stagger>
          <Stagger.Item>
            <Surface elevation="raised" className="p-6 sm:p-8">
              <div className="flex flex-col items-start gap-6 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <h2 className="font-display text-lg font-semibold text-[var(--ink)]">
                    Ready when you are
                  </h2>
                  <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-[var(--slate)]">
                    You&apos;ll join a video call, answer out loud, and the interviewer asks
                    follow-ups — so answer as you would to a person. You can only attempt this
                    once per repository.
                  </p>
                  {latest.data?.status === "failed" ? (
                    <p role="alert" className="mt-3 text-xs leading-relaxed text-[var(--failed)]">
                      Previous attempt failed: {latest.data.error}
                    </p>
                  ) : null}
                  {knownUnverified ? (
                    <p role="alert" className="mt-3 text-xs leading-relaxed text-[var(--flagged)]">
                      This repository has not been verified yet, so the interview can&apos;t
                      start. Finish verification on your profile first — the interview opens
                      once the repository is verified.
                    </p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
                  <Button
                    type="button"
                    size="lg"
                    onClick={() => start.mutate(projectId)}
                    isLoading={start.isPending}
                    disabled={start.isPending || knownUnverified}
                  >
                    <Video size={16} aria-hidden="true" /> Start interview
                  </Button>
                  <p className="text-xs text-[var(--muted)]">
                    {knownUnverified
                      ? "Waiting on repository verification"
                      : "You’ll check your camera and microphone first."}
                  </p>
                </div>
              </div>
              {startErrorMessage ? (
                <p role="alert" className="mt-4 text-xs text-[var(--failed)]">
                  {startErrorMessage}
                </p>
              ) : null}
            </Surface>
          </Stagger.Item>

          <Stagger.Item>
            <div className="grid gap-4 md:grid-cols-3">
              <Card title="How it works" padding="md">
                <ol className="space-y-3 text-sm text-[var(--slate)]">
                  <li className="flex gap-2.5">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--blue)]/12 text-[11px] font-semibold text-[var(--blue)]">
                      1
                    </span>
                    Check your camera and microphone in the green room.
                  </li>
                  <li className="flex gap-2.5">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--blue)]/12 text-[11px] font-semibold text-[var(--blue)]">
                      2
                    </span>
                    Talk through your code for about ten minutes.
                  </li>
                  <li className="flex gap-2.5">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--blue)]/12 text-[11px] font-semibold text-[var(--blue)]">
                      3
                    </span>
                    Get a scored report with the evidence behind it.
                  </li>
                </ol>
              </Card>

              <Card title="Before you start" padding="md">
                <ul className="space-y-2.5 text-sm text-[var(--slate)]">
                  <li className="flex gap-2">
                    <Mic size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    A quiet room and a working microphone — the interview is spoken.
                  </li>
                  <li className="flex gap-2">
                    <Clock size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    About ten minutes, uninterrupted. The clock keeps running if you leave.
                  </li>
                  <li className="flex gap-2">
                    <MessageSquare size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    Use Chrome or Edge for voice; other browsers fall back to typing.
                  </li>
                </ul>
              </Card>

              <Card title="How you’re scored" padding="md">
                <ul className="space-y-2.5 text-sm text-[var(--slate)]">
                  <li className="flex gap-2">
                    <Check size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    Technical accuracy, code understanding, problem solving, communication.
                  </li>
                  <li className="flex gap-2">
                    <Check size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    Every claim in your report is checked against the repository analysis.
                  </li>
                  <li className="flex gap-2">
                    <Check size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    The full transcript ships with the score, so you can check it.
                  </li>
                </ul>
              </Card>
            </div>
          </Stagger.Item>

          {otherVerified.length > 0 ? (
            <Stagger.Item>
              <Card
                title="Other verified repositories"
                subtitle="Each repository gets its own interview — pick one to open its lobby."
                padding="md"
              >
                <ul className="divide-y divide-[var(--rule-soft)]">
                  {otherVerified.map((item) => (
                    <li key={item.id}>
                      <Link
                        to={`/student/interview/${item.id}`}
                        className="flex items-center justify-between gap-3 py-3 text-sm transition-colors hover:text-[var(--ink)]"
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-[var(--ink)]">
                            {item.title}
                          </span>
                          {item.repo_url ? (
                            <span className="machine mt-0.5 block truncate text-xs text-[var(--muted)]">
                              {item.repo_url}
                            </span>
                          ) : null}
                        </span>
                        <span className="flex shrink-0 items-center gap-2 text-[var(--slate)]">
                          <VerificationBadge status={item.verification_status} />
                          <ArrowUpRight size={14} aria-hidden="true" />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            </Stagger.Item>
          ) : null}
        </Stagger>
      ) : null}

      {!(notStartedYet || latest.data?.status === "failed") ? (
        <InterviewStatusBody
          queryPending={query.isPending}
          hasData={Boolean(query.data)}
          interview={query.data?.interview ?? null}
          transcriptLength={query.data?.transcript.length ?? 0}
          onEnterRoom={() => navigate(roomPath)}
          reportState={report}
        />
      ) : null}
    </div>
  );
}

/** The repository this interview is about — the server's own record, with its
 * verification state shown as status, not decoration. */
function ProjectCard({ project }: { project: Project }) {
  const contribution = project.verification_payload?.contribution_share;
  return (
    <Surface className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-display text-lg font-semibold text-[var(--ink)]">{project.title}</h2>
            {project.is_primary ? <Badge variant="accent">Primary project</Badge> : null}
          </div>
          {project.description ? (
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-[var(--slate)]">
              {project.description}
            </p>
          ) : null}
        </div>
        <VerificationBadge status={project.verification_status} />
      </div>

      <dl className="mt-4 space-y-3 border-t border-[var(--rule-soft)] pt-4 text-sm">
        {project.repo_url ? (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <dt className="flex shrink-0 items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              <GitBranch size={13} aria-hidden="true" /> Repository
            </dt>
            <dd className="min-w-0">
              <a
                href={project.repo_url}
                target="_blank"
                rel="noreferrer"
                className="machine inline-flex max-w-full items-center gap-1.5 truncate text-[var(--blue)] hover:underline"
              >
                <span className="truncate">{project.repo_url}</span>
                <ExternalLink size={12} className="shrink-0" aria-hidden="true" />
              </a>
            </dd>
          </div>
        ) : null}
        {project.technologies.length > 0 ? (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <dt className="shrink-0 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              Detected in the code
            </dt>
            <dd className="flex min-w-0 flex-wrap gap-1.5">
              {project.technologies.map((tech) => (
                <span
                  key={tech}
                  className="machine rounded-full bg-[var(--panel-raised)] px-2.5 py-0.5 text-xs text-[var(--slate)]"
                >
                  {tech}
                </span>
              ))}
            </dd>
          </div>
        ) : null}
        {typeof contribution === "number" ? (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <dt className="shrink-0 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              Your share of the code
            </dt>
            <dd className="tabular-nums text-[var(--ink)]">
              {(contribution * 100).toFixed(0)}%
            </dd>
          </div>
        ) : null}
        {project.verification_status === "verified" && project.verified_at ? (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <dt className="flex shrink-0 items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              <ShieldCheck size={13} aria-hidden="true" /> Verified
            </dt>
            <dd className="text-[var(--slate)]">
              {new Date(project.verified_at).toLocaleDateString()}
            </dd>
          </div>
        ) : null}
      </dl>
    </Surface>
  );
}

function InterviewStatusBody({
  queryPending,
  hasData,
  interview,
  transcriptLength,
  onEnterRoom,
  reportState,
}: {
  queryPending: boolean;
  hasData: boolean;
  interview: InterviewSummary | null;
  transcriptLength: number;
  onEnterRoom: () => void;
  reportState: ReturnType<typeof useEvidenceReport>;
}) {
  if (queryPending || !hasData || !interview) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <>
      {interview.status === "pending" ? (
        <Surface elevation="raised" className="flex flex-col items-center gap-3 p-10 text-center">
          <Loader2 size={24} className="animate-spin text-[var(--blue)]" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--ink)]">Reading your repository…</p>
          <p className="max-w-md text-xs leading-relaxed text-[var(--slate)]">
            The interviewer is going through the stored analysis before you start. This usually
            takes a few seconds.
          </p>
        </Surface>
      ) : null}

      {/* An interview that is `in_progress` but not being sat is one the
          candidate walked out of — a closed tab, a dead battery. The session
          clock keeps running (`Interview.elapsed_seconds` is wall clock), so
          this says so plainly rather than implying the interview is paused and
          waiting for them. */}
      {interview.status === "in_progress" ? (
        <Surface elevation="raised" className="flex flex-col items-center gap-3 p-8 text-center sm:p-10">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--blue)]/12 text-[var(--blue)]">
            <Video size={22} aria-hidden="true" />
          </span>
          <h2 className="font-display text-xl font-semibold text-[var(--ink)]">
            Your interview is waiting
          </h2>
          <p className="max-w-md text-sm leading-relaxed text-[var(--slate)]">
            {transcriptLength > 0
              ? "You're partway through. Rejoin and you'll pick up exactly where you left off — nothing you said is lost. The clock keeps running while you're away."
              : "Your interviewer is ready. You'll check your camera and microphone before going in."}
          </p>
          <Button type="button" size="lg" onClick={onEnterRoom}>
            {transcriptLength > 0 ? "Rejoin interview" : "Enter interview room"}
          </Button>
        </Surface>
      ) : null}

      {interview.status === "evaluating" ? (
        <Surface elevation="raised" className="flex flex-col items-center gap-3 p-10 text-center">
          <Loader2 size={24} className="animate-spin text-[var(--blue)]" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--ink)]">Scoring the conversation…</p>
          <p className="max-w-md text-xs leading-relaxed text-[var(--slate)]">
            Everything you said is checked against the same repository analysis the questions came
            from.
          </p>
        </Surface>
      ) : null}

      {interview.status === "completed" ? (
        reportState.isPending ? (
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-96 w-full" />
          </div>
        ) : reportState.isError ? (
          <ErrorState
            title="Couldn't load the evidence report"
            description="The interview finished, but we couldn't fetch the report."
            action={
              <Button type="button" variant="secondary" size="sm" onClick={() => void reportState.refetch()}>
                Try again
              </Button>
            }
          />
        ) : reportState.data ? (
          <EvidenceReportView report={reportState.data} />
        ) : null
      ) : null}

      {interview.status === "failed" ? (
        <ErrorState title="This interview attempt failed" description={interview.error ?? "Something went wrong."} />
      ) : null}
    </>
  );
}
