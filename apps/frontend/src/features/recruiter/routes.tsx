import { Route } from "react-router-dom";

import { ProtectedRoute } from "@/features/auth";

import { RecruiterDashboardLayout } from "./DashboardLayout";
import { DashboardHome } from "./pages/DashboardHome";

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
    <Route index element={<DashboardHome />} />
  </Route>
);
