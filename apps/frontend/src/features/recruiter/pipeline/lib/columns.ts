import type { ApplicationStatus, PipelineBoard } from "../api/pipelineApi";

/**
 * The board's five columns, and how they sit over the server's six states.
 *
 * `hired` and `rejected` share the last column because they are the same
 * event to a recruiter scanning a board — this candidate is finished — and
 * two columns that are empty on all but a handful of jobs cost a fifth of the
 * horizontal space to say so. They are distinguished *inside* the column, by
 * colour and by a sub-heading, which is where the distinction actually
 * matters.
 *
 * **Tier A and Tier B are not in this file, and must not appear on this
 * board.** They are matching-engine vocabulary (`matching/tiers.py`): a
 * recruiter sees a candidate the system surfaced ("Matched") or a candidate
 * who applied ("Applied"), which is the distinction they can act on. Whether
 * the student was also emailed about it is not a property of the candidate.
 */

export type ColumnId = "matched" | "applied" | "shortlisted" | "interview_scheduled" | "closed";

/** A drop target. The closed column has two, which is why this is its own
 * type rather than `ColumnId` — dropping into "Offer" and dropping into
 * "Closed" are opposite decisions and cannot share a target. */
export type DropZoneId = "applied" | "shortlisted" | "interview_scheduled" | "hired" | "rejected";

export interface ColumnDef {
  id: ColumnId;
  header: string;
  /** Which server statuses feed this column, in render order. */
  statuses: ApplicationStatus[];
}

export const COLUMNS: ColumnDef[] = [
  { id: "matched", header: "MATCHED", statuses: [] },
  { id: "applied", header: "APPLIED", statuses: ["applied"] },
  { id: "shortlisted", header: "SHORTLISTED", statuses: ["shortlisted"] },
  { id: "interview_scheduled", header: "INTERVIEWING", statuses: ["interview_scheduled"] },
  { id: "closed", header: "OFFER · CLOSED", statuses: ["hired", "rejected"] },
];

/**
 * Which moves the board offers, mirroring
 * `domains/pipeline/models.py::ALLOWED_TRANSITIONS`.
 *
 * A UX shortcut, not a trust boundary: the server re-validates every
 * transition and 409s anything else, so the cost of this map being wrong is a
 * drop that bounces, never an illegal state. It exists so a card does not
 * offer a target that is going to be refused.
 *
 * **`matched` is absent, and that is not an oversight.** A matched candidate
 * has no `applications` row, and only the *student* can create one — Smart
 * Apply is theirs to use (`pipeline/router.py` mounts apply as a
 * student-only route). A recruiter dragging someone out of Matched would be
 * applying on their behalf, which is a thing this product does not do.
 */
export const ALLOWED_MOVES: Record<ApplicationStatus, DropZoneId[]> = {
  applied: ["shortlisted", "rejected"],
  shortlisted: ["interview_scheduled", "rejected"],
  interview_scheduled: ["hired", "rejected"],
  hired: [],
  rejected: [],
};

export function canMove(from: ApplicationStatus, to: DropZoneId): boolean {
  return ALLOWED_MOVES[from]?.includes(to) ?? false;
}

/** The column a status renders in. `hired` and `rejected` collapse onto the
 * shared final column; everything else is its own. */
export function columnFor(status: ApplicationStatus): ColumnId {
  return status === "hired" || status === "rejected" ? "closed" : (status as ColumnId);
}

/** The top-bar summary, e.g. `14 matched · 3 applied · 1 interviewing`.
 * Zero-count segments are dropped rather than rendered as "0 hired" — a
 * summary line is for orientation, and padding it with zeros makes the two
 * numbers that matter harder to find. */
export function summarise(board: PipelineBoard): string {
  const segments: [number, string][] = [
    [board.matched.length, "matched"],
    [board.applied.length, "applied"],
    [board.shortlisted.length, "shortlisted"],
    [board.interview_scheduled.length, "interviewing"],
    [board.hired.length, "hired"],
    [board.rejected.length, "closed"],
  ];
  const present = segments.filter(([count]) => count > 0);
  if (present.length === 0) return "No candidates yet";
  return present.map(([count, label]) => `${count} ${label}`).join(" · ");
}
