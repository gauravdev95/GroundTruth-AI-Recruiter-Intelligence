import { lazy } from "react";
import { Navigate, Route } from "react-router-dom";

import { ProtectedRoute } from "@/features/auth";

/** Code-split for the same reason as the student dashboard: the landing route
 * should not carry it. */
const RecruiterDashboardLayout = lazy(() =>
  import("./DashboardLayout").then((m) => ({ default: m.RecruiterDashboardLayout })),
);
const OverviewPage = lazy(() =>
  import("./pages/OverviewPage").then((m) => ({ default: m.OverviewPage })),
);
const JobsListPage = lazy(() =>
  import("./pages/JobsListPage").then((m) => ({ default: m.JobsListPage })),
);
const JobDetailPage = lazy(() =>
  import("./pages/JobDetailPage").then((m) => ({ default: m.JobDetailPage })),
);
const JobCreatePage = lazy(() =>
  import("./pages/JobCreatePage").then((m) => ({ default: m.JobCreatePage })),
);
const JobConfirmPage = lazy(() =>
  import("./pages/JobConfirmPage").then((m) => ({ default: m.JobConfirmPage })),
);
const KanbanBoardPage = lazy(() =>
  import("./pipeline/pages/KanbanBoardPage").then((m) => ({ default: m.KanbanBoardPage })),
);
const RecruiterApplicationDetailPage = lazy(() =>
  import("./pipeline/pages/ApplicationDetailPage").then((m) => ({ default: m.ApplicationDetailPage })),
);
const AnalyticsPage = lazy(() =>
  import("./analytics/pages/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })),
);
const CandidateEvidencePage = lazy(() =>
  import("./evidence/pages/CandidateEvidencePage").then((m) => ({ default: m.CandidateEvidencePage })),
);

/** Spread directly inside the root <Routes> in App.tsx. */
export const recruiterRoutes = (
  <Route
    path="/recruiter"
    element={
      <ProtectedRoute allow={["recruiter"]}>
        <RecruiterDashboardLayout />
      </ProtectedRoute>
    }
  >
    {/* One canonical dashboard URL, matching `/student/dashboard`, so the
        post-login redirect has a single target per role. */}
    <Route index element={<Navigate to="/recruiter/dashboard" replace />} />
    {/* The overview, not the jobs list. These used to be the same component
        at two URLs; they answer different questions — "what is happening"
        versus "show me all of them". */}
    <Route path="dashboard" element={<OverviewPage />} />
    <Route path="jobs" element={<JobsListPage />} />
    {/* Declared before `jobs/:jobId` so "new" is not matched as a job id.
        React Router v6 ranks static segments above dynamic ones regardless of
        order, but relying on that for a route whose dynamic sibling would
        otherwise 404 on a UUID parse is a subtlety the next reader should not
        have to know. */}
    <Route path="jobs/new" element={<JobCreatePage />} />
    <Route path="jobs/:jobId" element={<JobDetailPage />} />
    {/* The mandatory human-in-the-loop gate. Its own URL rather than a
        status-gated section of the job page, because it is a step in a flow
        with a back button and a forward button — and because a recruiter
        needs to be able to send it to a colleague. */}
    <Route path="jobs/:jobId/confirm" element={<JobConfirmPage />} />
    <Route path="jobs/:jobId/pipeline" element={<KanbanBoardPage />} />
    <Route path="applications/:applicationId" element={<RecruiterApplicationDetailPage />} />
    <Route path="candidates/:candidateProfileId/evidence" element={<CandidateEvidencePage />} />
    <Route path="analytics" element={<AnalyticsPage />} />
  </Route>
);
