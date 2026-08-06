import { apiClient } from "@/lib/apiClient";

/**
 * Types mirror `apps/backend/src/domains/student/schemas.py::ActivityFeedResponse`.
 *
 * The live analysis feed. Every field is derived server-side from rows a
 * worker actually wrote — there is deliberately no percentage anywhere in
 * this shape, because none of the stages can report one honestly. See the
 * backend's `domains/student/activity.py` for the full argument; the short
 * version is that a bar which fills on a timer is the loading-screen form of
 * the unverified claim this whole product exists to eliminate.
 */

const BASE = "/student/profile";

export type ActivityStageKey =
  | "github_account"
  | "repositories"
  | "coding_profiles"
  | "certificates"
  | "experience"
  | "indexing"
  | "interview";

/**
 * `inconclusive` is not a failure: the check ran and the evidence did not
 * hold. It renders amber, never red — the same distinction
 * `--verified`/`--flagged` carries everywhere else in the product.
 *
 * `skipped` means there was nothing to check (no certificates added), and is
 * distinct from `pending` so a row for work that will never happen does not
 * sit on screen looking stuck.
 */
export type ActivityStageState =
  | "pending"
  | "running"
  | "succeeded"
  | "inconclusive"
  | "failed"
  | "skipped";

export interface ActivityStage {
  key: ActivityStageKey;
  label: string;
  state: ActivityStageState;
  total: number;
  settled: number;
  started_at: string | null;
  finished_at: string | null;
  /** Present only on `failed`. Student-facing, never a stack trace. */
  detail: string | null;
}

export interface ActivityFeed {
  stages: ActivityStage[];
  /** The polling gate. Defined server-side so "finished" has one meaning. */
  is_running: boolean;
  /** Snapshot time. Elapsed durations are computed against this, not against
   * the device clock, so a skewed clock cannot render a negative duration. */
  as_of: string;
}

export async function fetchActivityFeed(): Promise<ActivityFeed> {
  const { data } = await apiClient.get<ActivityFeed>(`${BASE}/onboarding/activity`);
  return data;
}
