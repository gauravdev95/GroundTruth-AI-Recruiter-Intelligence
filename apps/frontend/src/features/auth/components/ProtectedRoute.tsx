import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuthContext } from "../context/AuthContext";
import type { UserRole } from "../api/authApi";

interface ProtectedRouteProps {
  allow: UserRole[];
  children: ReactNode;
}

/**
 * Role-guarded route wrapper, used by the student/recruiter dashboard shells.
 *
 * Unauthenticated users go to `/login` and carry the URL they were reaching
 * for, so signing in returns them there instead of dumping them on a dashboard
 * index. Authenticated users whose role isn't in `allow` get a dedicated 403
 * page rather than a silent redirect, so it's clear *why* they can't see the
 * page.
 */
export function ProtectedRoute({ allow, children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuthContext();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F6F7F9]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-ink" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (!allow.includes(user.role)) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
