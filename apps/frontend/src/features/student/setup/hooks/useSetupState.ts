import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { queryKeys } from "@/lib/queryKeys";

import { setupApi, type SetupState } from "../api/setupApi";

/**
 * The setup entry screen's single source of truth.
 *
 * Everything the screen renders — the five step circles, the completion pill,
 * whether a resume is already in flight — comes from here. The screen renders a
 * skeleton while this is pending rather than a default, because a default is a
 * wrong answer shown confidently: a returning student with a 60% profile would
 * see 0% for a beat and their completed steps drawn as empty.
 */
export function useSetupState() {
  return useQuery({
    queryKey: queryKeys.studentProfile.setupState(),
    queryFn: setupApi.getState,
  });
}

/**
 * Force the stepper and percentage to re-derive from the server.
 *
 * Used after a confirm or a manual save. Deliberately an invalidation and not a
 * local edit: `completion_percentage` and `current_step_index` are server
 * computations, and recomputing either on the client would be the one thing
 * this flow is not allowed to do.
 */
export function useInvalidateSetupState() {
  const queryClient = useQueryClient();
  return useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.studentProfile.setupState() }),
    [queryClient],
  );
}

/** Where a student mid-flow belongs, derived from the same server state the
 * screen renders. Kept here rather than in a component so the setup page and
 * the route guard cannot disagree about it. */
export function resumeFlowDestination(state: SetupState): "idle" | "analyzing" | "review" | "failed" {
  const { resume } = state;
  if (!resume.has_upload) return "idle";

  switch (resume.status) {
    case "uploaded":
    case "parsing":
      return "analyzing";
    case "failed":
      return "failed";
    case "parsed":
      // A confirmed or discarded draft is settled — sending the student back
      // to a review screen they already finished would look like the confirm
      // did not take.
      return resume.draft_status === "pending_review" ? "review" : "idle";
    default:
      return "idle";
  }
}
