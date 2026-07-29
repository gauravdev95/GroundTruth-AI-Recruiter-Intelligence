import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuthContext } from "../context/AuthContext";
import type { UserRole } from "../api/authApi";

interface ProtectedRouteProps {
  allow: UserRole[];
  children: ReactNode;
}

/**
 * Role-guarded route wrapper. No Phase 3 dashboards exist yet to guard —
 * this is the primitive those routes will use, exercised today only by
 * the placeholder authenticated landing state.
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

  if (!user || !allow.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
