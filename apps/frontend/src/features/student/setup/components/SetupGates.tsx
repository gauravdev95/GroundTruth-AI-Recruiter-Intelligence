import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Skeleton } from "@/components";

import { useSetupState } from "../hooks/useSetupState";

export const SETUP_PATH = "/student/profile/setup";

/**
 * The two halves of one rule, split because they guard different layouts.
 *
 * The rule: a student belongs in setup until they have **submitted** — until
 * `is_submitted` is true.
 *
 * This used to key on `meets_section_requirements` (sections 1 and 2
 * complete), and that was wrong in a way worth recording. It is *derived* from
 * rows, so it moves on its own: a verification worker rewriting a claim, or a
 * student clearing a field from the profile builder, could flip a student out
 * of the dashboard or into it without anybody deciding anything. It also ended
 * onboarding halfway through the flow — a student who saved section 2 was
 * redirected to the dashboard having never seen projects, certificates or
 * experience.
 *
 * `is_submitted` is an explicit act with a timestamp
 * (`CandidateProfile.onboarding_submitted_at`) and never moves by itself.
 * `meets_section_requirements` still exists and still matters — it is the bar
 * for whether Submit is *allowed* — but it is no longer the gate.
 *
 * It is also deliberately not keyed on `onboarding_choice`: answering the fork
 * is not the same as having a profile, and a choice-based gate waved a student
 * who abandoned their upload straight into an empty dashboard.
 *
 * Both halves read the same server value, so they cannot disagree and bounce a
 * student between two routes.
 */

/**
 * Guards the dashboard: an incomplete profile is sent into setup.
 *
 * Takes `children` rather than rendering an `<Outlet />` so it can wrap the
 * dashboard *layout* itself. A student who is about to be redirected then
 * never mounts the shell at all — which matters because the shell opens a
 * realtime socket on mount, and opening one for a student who is leaving
 * within the same tick is pure waste.
 */
export function RequireProfileSetup({ children }: { children: ReactNode }) {
  const setupState = useSetupState();

  // Nothing decisive until the answer is known. Guessing "incomplete" while
  // loading would flash setup at every returning student.
  if (setupState.isPending) {
    return <Skeleton className="m-6 h-64" />;
  }

  // A failed fetch must not lock a student out of their own dashboard — the
  // pages below render their own error states. Hence the optimistic default.
  if (setupState.data?.is_submitted ?? true) {
    return <>{children}</>;
  }

  return <Navigate to={SETUP_PATH} replace />;
}

/**
 * Guards setup: a student who has already submitted is sent to the dashboard,
 * so a finished student never sees the onboarding flow again — including by
 * typing the URL.
 *
 * Note what this no longer does: it does **not** fire when section 2 is
 * completed. Finishing a required section now advances the wizard to step 4,
 * not out of onboarding. The optional sections are part of the flow, and
 * everything stays editable afterwards at `/student/profile`.
 */
export function RedirectCompletedProfile() {
  const location = useLocation();
  const setupState = useSetupState();

  if (setupState.isPending) {
    return <Skeleton className="h-64 w-full" />;
  }

  // Pessimistic here, and optimistic in `RequireProfileSetup`, on purpose:
  // both defaults keep a student on the screen they are already looking at
  // when the fetch fails, rather than throwing them somewhere on bad data.
  if (setupState.data?.is_submitted ?? false) {
    return <Navigate to="/student/dashboard" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
