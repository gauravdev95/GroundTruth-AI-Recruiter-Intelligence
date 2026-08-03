import { lazy } from "react";
import { Navigate, Route } from "react-router-dom";

import { ProtectedRoute } from "@/features/auth";

/** Code-split for the same reason as the student dashboard: the landing route
 * should not carry it. */
const RecruiterDashboardLayout = lazy(() =>
  import("./DashboardLayout").then((m) => ({ default: m.RecruiterDashboardLayout })),
);
const JobsListPage = lazy(() =>
  import("./pages/JobsListPage").then((m) => ({ default: m.JobsListPage })),
);
const JobDetailPage = lazy(() =>
  import("./pages/JobDetailPage").then((m) => ({ default: m.JobDetailPage })),
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
    <Route path="dashboard" element={<JobsListPage />} />
    <Route path="jobs" element={<JobsListPage />} />
    <Route path="jobs/:jobId" element={<JobDetailPage />} />
    <Route path="jobs/:jobId/pipeline" element={<KanbanBoardPage />} />
    <Route path="applications/:applicationId" element={<RecruiterApplicationDetailPage />} />
    <Route path="candidates/:candidateProfileId/evidence" element={<CandidateEvidencePage />} />
    <Route path="analytics" element={<AnalyticsPage />} />
  </Route>
);
