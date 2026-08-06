import type { PipelineBoard } from "../api/pipelineApi";

/**
 * CSV of the pipeline as it currently stands.
 *
 * **Exports what is on screen, not what is in the database.** The board the
 * recruiter is looking at is the board they mean to export, including any
 * optimistic move that has not settled — re-fetching first would produce a
 * file that disagrees with the screen for no benefit.
 *
 * The candidate's name is deliberately absent, because the board never
 * receives it (`pipeline/service.py::get_pipeline` returns `headline`). An
 * export is exactly the wrong place to start widening what a recruiter can
 * take out of the system about people who have not spoken to them yet.
 */

const COLUMNS = [
  "stage",
  "candidate_profile_id",
  "headline",
  "match_score",
  "score_at_apply",
  "verified",
  "matched_skills",
  "reasoning",
  "applied_at",
  "status_updated_at",
] as const;

/**
 * RFC 4180 quoting. Every field is quoted unconditionally rather than only
 * when it contains a delimiter: the reasoning string contains commas by
 * construction ("Matches on Rust, PostgreSQL, …"), so conditional quoting
 * would be the common path anyway, and a single rule cannot be applied
 * inconsistently.
 */
function cell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return '""';
  return `"${String(value).replace(/"/g, '""')}"`;
}

export function boardToCsv(board: PipelineBoard): string {
  const rows: string[] = [COLUMNS.map(cell).join(",")];

  for (const candidate of board.matched) {
    rows.push(
      [
        cell("matched"),
        cell(candidate.candidate_profile_id),
        cell(candidate.headline),
        cell(Math.round(candidate.match_score)),
        cell(null),
        cell(candidate.is_verified),
        cell(candidate.matched_skills.join(" · ")),
        cell(candidate.reasoning),
        cell(null),
        cell(null),
      ].join(","),
    );
  }

  const applicationStages = [
    ["applied", board.applied],
    ["shortlisted", board.shortlisted],
    ["interview_scheduled", board.interview_scheduled],
    ["hired", board.hired],
    ["rejected", board.rejected],
  ] as const;

  for (const [stage, applications] of applicationStages) {
    for (const application of applications) {
      rows.push(
        [
          cell(stage),
          cell(application.candidate_profile_id),
          cell(application.headline),
          cell(application.match_score === null ? null : Math.round(application.match_score)),
          cell(application.score_at_apply === null ? null : Math.round(application.score_at_apply)),
          cell(application.is_verified),
          cell(application.matched_skills.join(" · ")),
          cell(application.reasoning),
          cell(application.applied_at),
          cell(application.status_updated_at),
        ].join(","),
      );
    }
  }

  return rows.join("\r\n");
}

/** Filenames are `pipeline-<slug>-<date>.csv`; a recruiter exporting three
 * jobs in a morning should not end up with `pipeline (2).csv`. */
export function downloadBoardCsv(board: PipelineBoard, jobTitle: string): void {
  const slug =
    jobTitle
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 48) || "job";
  const stamp = new Date().toISOString().slice(0, 10);

  // The BOM is for Excel, which otherwise reads UTF-8 CSV as the system
  // codepage and renders any non-ASCII skill name as mojibake.
  const blob = new Blob(["﻿", boardToCsv(board)], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `pipeline-${slug}-${stamp}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
