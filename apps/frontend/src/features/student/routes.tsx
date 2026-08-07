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
const SetupStageLayout = lazy(() =>
  import("./setup/components/SetupStageLayout").then((m) => ({ default: m.SetupStageLayout })),
);
const StageBasicInfoPage = lazy(() =>
  import("./setup/pages/StageBasicInfoPage").then((m) => ({ default: m.StageBasicInfoPage })),
);
const StageGithubPage = lazy(() =>
  import("./setup/pages/StageGithubPage").then((m) => ({ default: m.StageGithubPage })),
);
const StageProjectsPage = lazy(() =>
  import("./setup/pages/StageProjectsPage").then((m) => ({ default: m.StageProjectsPage })),
);
const StageCodingPage = lazy(() =>
  import("./setup/pages/StageCodingPage").then((m) => ({ default: m.StageCodingPage })),
);
const StageCertificatesPage = lazy(() =>
  import("./setup/pages/StageCertificatesPage").then((m) => ({ default: m.StageCertificatesPage })),
);
const StageExperiencePage = lazy(() =>
  import("./setup/pages/StageExperiencePage").then((m) => ({ default: m.StageExperiencePage })),
);
const StageReviewPage = lazy(() =>
  import("./setup/pages/StageReviewPage").then((m) => ({ default: m.StageReviewPage })),
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
/* Its own chunk, and worth it: the room pulls in the media, speech and
   integrity layers plus a stylesheet, none of which any other screen touches
   and none of which a student who never sits an interview should download. */
const InterviewRoomPage = lazy(() =>
  import("./interview/room/pages/InterviewRoomPage").then((m) => ({ default: m.InterviewRoomPage })),
);
const JobFeedPage = lazy(() =>
  import("./matches/pages/JobFeedPage").then((m) => ({ default: m.JobFeedPage })),
);
const StudentJobDetailPage = lazy(() =>
  import("./matches/pages/JobDetailPage").then((m) => ({ default: m.JobDetailPage })),
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
      {/* A submitted profile is redirected out, so the flow cannot be
          re-entered by typing the URL. */}
      <Route element={<RedirectCompletedProfile />}>
        {/* Stage 0 — the fork. Its own route rather than a stage inside the
            layout: it is a full-page choice with no progress bar above it,
            because there is nothing to step through until it is answered. */}
        <Route index element={<ProfileSetupPage />} />
        {/* Both paths are plain routes. Choosing one writes no flag, and
            switching between them clears nothing — the resume path only ever
            produces a draft until the student confirms it. */}
        <Route path="resume" element={<SetupResumePage />} />

        {/* Stages 1-7, one route each.

            One route per stage rather than one wizard holding a step index:
            the index version left the flow entirely on the back button, and a
            refresh mid-setup reopened at whichever step the server thought was
            next rather than the one being looked at. A URL per stage makes
            both work, and makes a half-finished setup a link the student can
            reopen on another device.

            The slugs are the spec's own (`basic-info`, `github`, `projects`,
            `coding-profile`, `certificates`, `experience`, `review`); only the
            prefix differs, because this subtree already sits inside the
            candidate-only guard and `RedirectCompletedProfile`. */}
        <Route element={<SetupStageLayout />}>
          <Route path="basic-info" element={<StageBasicInfoPage />} />
          <Route path="github" element={<StageGithubPage />} />
          <Route path="projects" element={<StageProjectsPage />} />
          <Route path="coding-profile" element={<StageCodingPage />} />
          <Route path="certificates" element={<StageCertificatesPage />} />
          <Route path="experience" element={<StageExperiencePage />} />
          <Route path="review" element={<StageReviewPage />} />
        </Route>

        {/* The wizard's old single URL. Kept as a redirect rather than deleted:
            the resume-confirm path sends students here, and any link already in
            the wild points at it. Stage 1 is where it used to open. */}
        <Route
          path="manual"
          element={<Navigate to="/student/profile/setup/basic-info" replace />}
        />
      </Route>
    </Route>

    {/* Replaced by `/student/profile/setup`. Kept as a redirect rather than
        deleted so in-flight sessions, bookmarks and any already-sent link do
        not 404 — there is exactly one fork now, and this points at it. */}
    <Route path="/student/onboarding" element={<Navigate to="/student/profile/setup" replace />} />

    {/* The interview room.

        Deliberately a sibling of the dashboard branch rather than a child of
        it, so it renders *without* `StudentDashboardLayout`. A live interview
        must own the whole viewport — a sidebar next to a video call is five
        invitations to leave in the middle of a question — and the shell also
        opens the app-wide realtime socket, which would be free to pop a
        notification toast over somebody being assessed.

        Same two guards as the dashboard, in the same order: this is still a
        candidate-only screen and still requires a finished profile. Only the
        chrome differs. */}
    <Route
      path="/student/interview/:projectId/room"
      element={
        <ProtectedRoute allow={["candidate"]}>
          <RequireProfileSetup>
            <InterviewRoomPage />
          </RequireProfileSetup>
        </ProtectedRoute>
      }
    />

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
      {/* `jobs/:jobId`, not `matches/:jobId`: the page shows a *job*, and the
          match is the reason the student may see it. The High Match card and
          the feed both link here. */}
      <Route path="jobs/:jobId" element={<StudentJobDetailPage />} />
      <Route path="applications" element={<MyApplicationsPage />} />
      <Route path="applications/:applicationId" element={<ApplicationDetailPage />} />
    </Route>

    {/* Bookmarks and already-sent notification emails still point at the old
        prefix; `*` carries the rest of the path through unchanged. */}
    <Route path="/candidate/*" element={<LegacyCandidateRedirect />} />
  </>
);
