import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Skeleton } from "@/components";

import { useSetupState } from "../hooks/useSetupState";

export const SETUP_PATH = "/student/profile/setup";

/**
 * The two halves of one rule, split because they guard different layouts.
 *
 * The rule: a student belongs in setup exactly while
 * `meets_section_requirements` is false — sections 1 and 2 not both complete.
 *
 * It is deliberately **not** keyed on `onboarding_choice`. Answering the fork
 * is not the same as having a profile: a student who picked "resume" yesterday
 * and abandoned the upload has chosen a path and completed nothing, and a
 * choice-based gate waved exactly that student past setup into an empty
 * dashboard. Choice is telemetry. Completeness is the gate.
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
  if (setupState.data?.meets_section_requirements ?? true) {
    return <>{children}</>;
  }

  return <Navigate to={SETUP_PATH} replace />;
}

/**
 * Guards setup: a profile that already meets the section requirements is sent
 * to the dashboard, so a finished student never sees the entry screen again —
 * including by typing the URL.
 *
 * This also fires the moment a student completes section 2 inside the flow,
 * which is the specified end of setup: sections 1 and 2 complete means
 * `/student/dashboard`. Optional sections 3-5 stay editable at
 * `/student/profile`.
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
  if (setupState.data?.meets_section_requirements ?? false) {
    return <Navigate to="/student/dashboard" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
