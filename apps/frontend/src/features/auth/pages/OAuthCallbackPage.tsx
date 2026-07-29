import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { refreshAccessToken } from "@/lib/apiClient";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { authApi } from "../api/authApi";
import { useAuthContext } from "../context/AuthContext";

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
        navigate("/", { replace: true });
      } catch {
        if (!cancelled) setError("Google sign-in didn't complete. Please try again.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [searchParams, navigate, setSession]);

  if (error) {
    return (
      <AuthLayout title="Sign-in failed">
        <div className="flex flex-col gap-4">
          <AlertBanner message={error} />
          <Link
            to="/login/candidate"
            className="text-center text-sm font-medium text-indigo-600 hover:text-indigo-500"
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
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
      </div>
    </AuthLayout>
  );
}
