import { isAxiosError } from "axios";
import { ArrowLeft, Loader2, Video } from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button, ErrorState, Skeleton } from "@/components";

import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
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
 */
export function InterviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const latest = useLatestInterview(projectId ?? "");
  const start = useStartInterview();

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

  const backLink = (
    <Link
      to="/student/profile"
      className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] hover:text-[var(--ink)]"
    >
      <ArrowLeft size={14} aria-hidden="true" /> Back to profile
    </Link>
  );

  if (latest.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
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

  // No attempt exists yet, or the most recent one failed — either way, offer
  // to start (a fresh `start` call is allowed after `failed`; see
  // `interview/service.py::_BLOCKING_STATUSES`). Once `start` succeeds it
  // overwrites this same cache entry with the new `pending` interview, so
  // this branch naturally stops matching on the next render.
  if (notStartedYet || latest.data?.status === "failed") {
    return (
      <div className="space-y-4">
        {backLink}
        <div className="space-y-4 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-8 text-center">
          <h1 className="font-display text-xl font-semibold text-[var(--ink)]">Code-grounded AI interview</h1>
          <p className="mx-auto max-w-md text-sm text-[var(--slate)]">
            A ten-minute spoken conversation about this repository with an interviewer that has already
            read it. You&apos;ll join a video call, answer out loud, and it asks follow-ups — so answer as
            you would to a person. Nothing generic: every question traces back to something GroundTruth
            actually found in your code. You can only attempt this once per repository.
          </p>
          <p className="mx-auto max-w-md text-xs text-[var(--muted)]">
            You&apos;ll check your camera and microphone before the interview starts.
          </p>
          {latest.data?.status === "failed" ? (
            <p className="text-xs text-[var(--failed)]">Previous attempt failed: {latest.data.error}</p>
          ) : null}
          <Button
            type="button"
            onClick={() => start.mutate(projectId)}
            isLoading={start.isPending}
            disabled={start.isPending}
          >
            Start interview
          </Button>
          {startErrorMessage ? (
            <p role="alert" className="text-xs text-[var(--failed)]">
              {startErrorMessage}
            </p>
          ) : null}
        </div>
      </div>
    );
  }

  if (query.isPending || !query.data) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const { interview } = query.data;

  return (
    <div className="space-y-4">
      {backLink}

      {interview.status === "pending" ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-10 text-center">
          <Loader2 size={24} className="animate-spin text-[var(--ink)]" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--ink)]">Reading your repository…</p>
          <p className="text-xs text-[var(--slate)]">
            The interviewer is going through the stored analysis before you start. This usually takes a few
            seconds.
          </p>
        </div>
      ) : null}

      {/* An interview that is `in_progress` but not being sat is one the
          candidate walked out of — a closed tab, a dead battery. The session
          clock keeps running (`Interview.elapsed_seconds` is wall clock), so
          this says so plainly rather than implying the interview is paused and
          waiting for them. */}
      {interview.status === "in_progress" ? (
        <div className="space-y-4 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-8 text-center">
          <Video size={22} className="mx-auto text-[var(--ink)]" aria-hidden="true" />
          <h1 className="font-display text-xl font-semibold text-[var(--ink)]">
            Your interview is waiting
          </h1>
          <p className="mx-auto max-w-md text-sm text-[var(--slate)]">
            {query.data.transcript.length > 0
              ? "You're partway through. Rejoin and you'll pick up exactly where you left off — nothing you said is lost. The clock keeps running while you're away."
              : "Your interviewer is ready. You'll check your camera and microphone before going in."}
          </p>
          <Button type="button" onClick={() => navigate(roomPath)}>
            {query.data.transcript.length > 0 ? "Rejoin interview" : "Enter interview room"}
          </Button>
        </div>
      ) : null}

      {interview.status === "evaluating" ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-10 text-center">
          <Loader2 size={24} className="animate-spin text-[var(--ink)]" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--ink)]">Scoring the conversation…</p>
          <p className="text-xs text-[var(--slate)]">
            Everything you said is checked against the same repository analysis the questions came from.
          </p>
        </div>
      ) : null}

      {interview.status === "completed" ? (
        report.isPending ? (
          <Skeleton className="h-96 w-full" />
        ) : report.isError ? (
          <ErrorState
            title="Couldn't load the evidence report"
            description="The interview finished, but we couldn't fetch the report."
            action={
              <Button type="button" variant="secondary" size="sm" onClick={() => void report.refetch()}>
                Try again
              </Button>
            }
          />
        ) : report.data ? (
          <EvidenceReportView report={report.data} />
        ) : null
      ) : null}

      {interview.status === "failed" ? (
        <ErrorState title="This interview attempt failed" description={interview.error ?? "Something went wrong."} />
      ) : null}
    </div>
  );
}
