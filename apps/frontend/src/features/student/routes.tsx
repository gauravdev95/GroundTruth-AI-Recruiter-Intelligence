import { lazy } from "react";
import { Navigate, Route } from "react-router-dom";

import { ProtectedRoute } from "@/features/auth";

import { LegacyCandidateRedirect } from "./LegacyCandidateRedirect";
// Eagerly imported alongside `ProtectedRoute`: these are guards that decide
// whether any of the lazy pages below render at all.
import { RedirectCompletedProfile, RequireProfileSetup } from "./setup/components/SetupGates";

/**
 * Code-split: a signed-out visitor on the landing page should not download a
 * dashboard. `ProtectedRoute` stays eagerly imported — it is the guard that
 * decides whether to render any of this, and it is shared with the recruiter
 * routes.
 */
const StudentDashboardLayout = lazy(() =>
  import("./DashboardLayout").then((m) => ({ default: m.StudentDashboardLayout })),
);
const SetupLayout = lazy(() =>
  import("./setup/components/SetupLayout").then((m) => ({ default: m.SetupLayout })),
);
const ProfileSetupPage = lazy(() =>
  import("./setup/pages/ProfileSetupPage").then((m) => ({ default: m.ProfileSetupPage })),
);
const SetupResumePage = lazy(() =>
  import("./setup/pages/SetupResumePage").then((m) => ({ default: m.SetupResumePage })),
);
const SetupManualPage = lazy(() =>
  import("./setup/pages/SetupManualPage").then((m) => ({ default: m.SetupManualPage })),
);
const DashboardHome = lazy(() =>
  import("./pages/DashboardHome").then((m) => ({ default: m.DashboardHome })),
);
const ProfileBuilderPage = lazy(() =>
  import("./pages/ProfileBuilderPage").then((m) => ({ default: m.ProfileBuilderPage })),
);
const ResumeImportPage = lazy(() =>
  import("./resume/pages/ResumeImportPage").then((m) => ({ default: m.ResumeImportPage })),
);
const InterviewPage = lazy(() =>
  import("./interview/pages/InterviewPage").then((m) => ({ default: m.InterviewPage })),
);
const JobFeedPage = lazy(() =>
  import("./matches/pages/JobFeedPage").then((m) => ({ default: m.JobFeedPage })),
);
const MyApplicationsPage = lazy(() =>
  import("./applications/pages/MyApplicationsPage").then((m) => ({ default: m.MyApplicationsPage })),
);
const ApplicationDetailPage = lazy(() =>
  import("./applications/pages/ApplicationDetailPage").then((m) => ({ default: m.ApplicationDetailPage })),
);

/**
 * Spread directly inside the root <Routes> in App.tsx.
 *
 * The URL says "student" and the API says "candidate", deliberately: the
 * user-facing word for this audience is "student", while `candidate` is the
 * domain term throughout the backend (`domains/student/` serving
 * `CandidateProfile`) and renaming that would touch every table and route for
 * no behavioural gain.
 *
 * Two branches, each with its own layout and its own half of one gate:
 *
 * - `/student/profile/setup/*` — the post-signup flow, on `SetupLayout`. It is
 *   not inside the dashboard shell because a student mid-setup has nothing to
 *   navigate to; a sidebar there would offer five destinations that are all
 *   empty or gated.
 * - `/student/*` — the dashboard, on `StudentDashboardLayout`.
 *
 * The setup branch is declared first for readability only. React Router ranks
 * by specificity rather than order, so `/student/profile/setup` beats the
 * dashboard's `/student` + `profile` child regardless of position.
 */
export const studentRoutes = (
  <>
    <Route
      path="/student/profile/setup"
      element={
        <ProtectedRoute allow={["candidate"]}>
          <SetupLayout />
        </ProtectedRoute>
      }
    >
      {/* A finished profile is redirected out, so the entry screen cannot be
          re-entered by typing the URL. */}
      <Route element={<RedirectCompletedProfile />}>
        <Route index element={<ProfileSetupPage />} />
        {/* Both paths are plain routes. Choosing one writes no flag, and
            switching between them clears nothing — the resume path only ever
            produces a draft until the student confirms it. */}
        <Route path="resume" element={<SetupResumePage />} />
        <Route path="manual" element={<SetupManualPage />} />
      </Route>
    </Route>

    {/* Replaced by `/student/profile/setup`. Kept as a redirect rather than
        deleted so in-flight sessions, bookmarks and any already-sent link do
        not 404 — there is exactly one fork now, and this points at it. */}
    <Route path="/student/onboarding" element={<Navigate to="/student/profile/setup" replace />} />

    <Route
      path="/student"
      element={
        /* The gate wraps the layout rather than sitting inside it, so a
           student headed for setup never mounts the dashboard shell — and
           never opens the realtime socket the shell opens on mount. */
        <ProtectedRoute allow={["candidate"]}>
          <RequireProfileSetup>
            <StudentDashboardLayout />
          </RequireProfileSetup>
        </ProtectedRoute>
      }
    >
      <Route index element={<Navigate to="/student/dashboard" replace />} />
      <Route path="dashboard" element={<DashboardHome />} />
      <Route path="profile" element={<ProfileBuilderPage />} />
      <Route path="resume" element={<ResumeImportPage />} />
      <Route path="interview/:projectId" element={<InterviewPage />} />
      <Route path="matches" element={<JobFeedPage />} />
      <Route path="applications" element={<MyApplicationsPage />} />
      <Route path="applications/:applicationId" element={<ApplicationDetailPage />} />
    </Route>

    {/* Bookmarks and already-sent notification emails still point at the old
        prefix; `*` carries the rest of the path through unchanged. */}
    <Route path="/candidate/*" element={<LegacyCandidateRedirect />} />
  </>
);
