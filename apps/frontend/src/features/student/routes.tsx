import { Route } from "react-router-dom";

import { ProtectedRoute } from "@/features/auth";

import { StudentDashboardLayout } from "./DashboardLayout";
import { DashboardHome } from "./pages/DashboardHome";

/** Spread directly inside the root <Routes> in App.tsx. Route path uses
 * "candidate" (matching the URL convention already established by
 * `/login/candidate`), while the feature folder is named "student" per
 * the existing `apps/backend/src/domains/student/` convention. */
export const studentRoutes = (
  <Route
    path="/candidate"
    element={
      <ProtectedRoute allow={["candidate"]}>
        <StudentDashboardLayout />
      </ProtectedRoute>
    }
  >
    <Route index element={<DashboardHome />} />
  </Route>
);
