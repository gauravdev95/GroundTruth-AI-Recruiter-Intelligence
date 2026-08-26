import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { refreshAccessToken } from "@/lib/apiClient";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { authApi } from "../api/authApi";
import { useAuthContext } from "../context/AuthContext";
import { dashboardPathForRole } from "../lib/dashboardPath";

/** Google redirects here after the backend has already set session cookies. */
export function OAuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setSession } = useAuthContext();
  const [error, setError] = useState<string | null>(
    searchParams.get("error") ? "Google sign-in didn't complete. Please try again." : null,
  );

  useEffect(() => {
    if (searchParams.get("error")) return;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) setError("Sign-in is taking too long. Please try again.");
    }, 15_000);

    void (async () => {
      const token = await refreshAccessToken();
      if (cancelled) return;
      if (!token) {
        setError("Google sign-in didn't complete. Please try again.");
        return;
      }
      try {
        const user = await authApi.me();
        if (cancelled) return;
        setSession(user, token);
        navigate(dashboardPathForRole(user.role), { replace: true });
      } catch {
        if (!cancelled) setError("Google sign-in didn't complete. Please try again.");
      }
    })();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [searchParams, navigate, setSession]);

  if (error) {
    return (
      <AuthLayout title="Sign-in failed">
        <div className="flex flex-col gap-4">
          <AlertBanner message={error} />
          <Link
            to="/login"
            className="text-center text-sm font-medium text-[var(--ink)] underline decoration-[var(--rule)] underline-offset-2 transition-colors hover:decoration-[var(--ink)]"
          >
            Back to login
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Signing you in…">
      <div className="flex justify-center py-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--rule)] border-t-[var(--violet)]" />
      </div>
    </AuthLayout>
  );
}
