import type { ApplicationStatus } from "../api/applicationsApi";

/**
 * The recruitment stage timeline, derived from the one thing the student
 * API records about an application's progress: its current `status` plus
 * `applied_at` and `status_updated_at`.
 *
 * The backend's `ALLOWED_TRANSITIONS` (`pipeline/models.py`) is a strict
 * linear path — applied → shortlisted → interview_scheduled → hired, with
 * no jumps — so a non-rejected status implies every earlier stage was
 * passed through. That is the only inference this module makes, and it is
 * the backend's own rule, not a guess.
 *
 * `rejected` is reachable from any of the first three stages, and the
 * student API carries no record of *which* one, so a rejected application
 * shows only what is known: Applied (with its date) and the terminal
 * "Not selected" step (with `status_updated_at`). The middle stages are
 * not shown as reached or unreached — either claim would invent history.
 */

export interface TimelineStage {
  id: string;
  label: string;
  /** Reached on the way to the current status. */
  state: "done" | "current" | "upcoming";
  /** Only where the API supplies a real timestamp for this step. */
  dateLabel?: string;
  date?: string;
}

const FORWARD_STAGES: { id: ApplicationStatus; label: string }[] = [
  { id: "applied", label: "Applied" },
  { id: "shortlisted", label: "Shortlisted" },
  { id: "interview_scheduled", label: "Interview scheduled" },
  { id: "hired", label: "Hired" },
];

export function buildStageTimeline(
  status: ApplicationStatus,
  appliedAt: string,
  statusUpdatedAt: string,
): TimelineStage[] {
  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });

  if (status === "rejected") {
    return [
      {
        id: "applied",
        label: "Applied",
        state: "done",
        dateLabel: "Applied",
        date: formatDate(appliedAt),
      },
      {
        id: "rejected",
        label: "Not selected",
        state: "current",
        dateLabel: "Decision",
        date: formatDate(statusUpdatedAt),
      },
    ];
  }

  const currentIndex = FORWARD_STAGES.findIndex((stage) => stage.id === status);
  return FORWARD_STAGES.map((stage, index) => {
    if (index < currentIndex) {
      return { id: stage.id, label: stage.label, state: "done" as const };
    }
    if (index === currentIndex) {
      return {
        id: stage.id,
        label: stage.label,
        state: "current" as const,
        dateLabel: stage.id === "applied" ? "Applied" : "Updated",
        date: formatDate(stage.id === "applied" ? appliedAt : statusUpdatedAt),
      };
    }
    return { id: stage.id, label: stage.label, state: "upcoming" as const };
  });
}
