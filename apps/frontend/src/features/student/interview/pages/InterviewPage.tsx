import { isAxiosError } from "axios";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { Button, ErrorState, Skeleton, useToast } from "@/components";

import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { EvidenceReportView } from "../components/EvidenceReportView";
import { TimedQuestion } from "../components/TimedQuestion";
import {
  useEvidenceReport,
  useInterviewState,
  useLatestInterview,
  useStartInterview,
  useSubmitAnswer,
} from "../hooks/useInterview";

/**
 * `:projectId` (not `:interviewId`) — a repository has at most one
 * non-failed interview attempt ever, so the project is the stable thing to
 * link to from `ProjectsForm`; the interview itself is resolved underneath.
 */
export function InterviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { showToast } = useToast();

  const latest = useLatestInterview(projectId ?? "");
  const start = useStartInterview();

  const notStartedYet = latest.isError && isAxiosError(latest.error) && latest.error.response?.status === 404;
  const startFailed =
    latest.isError && !(isAxiosError(latest.error) && latest.error.response?.status === 404);

  const interviewId = latest.data?.id ?? (start.data && start.data.project_id === projectId ? start.data.id : null);
  const state = useInterviewState(interviewId);
  const submitAnswer = useSubmitAnswer(interviewId ?? "");
  const report = useEvidenceReport(interviewId ?? "", state.data?.interview.status === "completed");

  // A repository-verification-required 409 is the one failure worth its own
  // message; everything else falls back to the generic one.
  const startErrorMessage = start.isError
    ? getProfileErrorMessage(start.error, "Could not start the interview.")
    : null;

  useEffect(() => {
    if (submitAnswer.isError) {
      showToast(getProfileErrorMessage(submitAnswer.error, "Could not submit that answer."), "error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submitAnswer.isError]);

  if (!projectId) return null;

  const backLink = (
    <Link
      to="/student/profile"
      className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink"
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
        <div className="space-y-4 rounded-2xl border border-rule bg-white p-8 text-center">
          <h1 className="font-display text-xl font-semibold text-ink">Code-grounded AI interview</h1>
          <p className="mx-auto max-w-md text-sm text-slate-500">
            5-7 questions generated from the stored analysis of this repository — nothing generic, every
            question traces back to something GroundTruth actually found in your code. Answer each one
            under a time limit; you can only attempt this once per repository.
          </p>
          {latest.data?.status === "failed" ? (
            <p className="text-xs text-red-500">Previous attempt failed: {latest.data.error}</p>
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
            <p role="alert" className="text-xs text-red-500">
              {startErrorMessage}
            </p>
          ) : null}
        </div>
      </div>
    );
  }

  if (state.isPending || !state.data) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const { interview, current_question: currentQuestion, answered_count: answeredCount } = state.data;

  return (
    <div className="space-y-4">
      {backLink}

      {interview.status === "pending" ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-rule bg-white p-10 text-center">
          <Loader2 size={24} className="animate-spin text-ink" aria-hidden="true" />
          <p className="text-sm font-medium text-ink">Writing your questions…</p>
          <p className="text-xs text-slate-500">
            Grounded in the repository's stored analysis. This usually takes a few seconds.
          </p>
        </div>
      ) : null}

      {interview.status === "in_progress" && currentQuestion ? (
        <TimedQuestion
          key={currentQuestion.id}
          question={currentQuestion}
          questionNumber={answeredCount + 1}
          totalQuestions={interview.question_count}
          isSubmitting={submitAnswer.isPending}
          onSubmit={(transcript, timeTakenSeconds) =>
            submitAnswer.mutate({ questionId: currentQuestion.id, transcript, timeTakenSeconds })
          }
        />
      ) : null}

      {interview.status === "evaluating" ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-rule bg-white p-10 text-center">
          <Loader2 size={24} className="animate-spin text-ink" aria-hidden="true" />
          <p className="text-sm font-medium text-ink">Scoring your answers…</p>
          <p className="text-xs text-slate-500">
            Every answer is checked against the same repository analysis its question was grounded in.
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
