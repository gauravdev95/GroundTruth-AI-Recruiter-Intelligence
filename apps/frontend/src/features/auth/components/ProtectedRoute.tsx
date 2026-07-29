import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuthContext } from "../context/AuthContext";
import type { UserRole } from "../api/authApi";

interface ProtectedRouteProps {
  allow: UserRole[];
  children: ReactNode;
}

/**
 * Role-guarded route wrapper, used by the candidate/recruiter dashboard
 * shells. Unauthenticated users are sent to "/" — this app's actual
 * sign-in entry point is the landing page's nav "Login" button +
 * `RoleSelectModal`; there is no standalone `/login` route. Authenticated
 * users whose role isn't in `allow` get a dedicated 403 page instead of a
 * silent redirect, so it's clear *why* they can't see the page.
 */
export function ProtectedRoute({ allow, children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuthContext();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F6F7F9]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/" replace />;
  }

  if (!allow.includes(user.role)) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
