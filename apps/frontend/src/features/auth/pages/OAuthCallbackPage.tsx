import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { refreshAccessToken } from "@/lib/apiClient";

import { AlertBanner } from "../components/AlertBanner";
import { AuthHero, heroLinkClass } from "../components/AuthHero";
import { authApi } from "../api/authApi";
import { useAuthContext } from "../context/AuthContext";
import { dashboardPathForRole } from "../lib/dashboardPath";

const PITCH = [
  "Google confirms your identity; GroundTruth does the rest.",
  "Your role decides where you land — student or recruiter.",
  "No password to type: the session is already being created.",
] as const;

/**
 * Google redirects here after the backend has already set session cookies.
 *
 * Phase 3 moved this off the quiet `AuthLayout` card onto the split-screen
 * hero, so the OAuth round-trip never leaves the product's visual world. The
 * refresh-then-`me` handshake, the 15s timeout and the error handling are
 * unchanged — only the shell moved.
 */
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
      <AuthHero
        eyebrow="Google sign-in"
        headline="Sign-in failed"
        lead="Google didn't finish handing you over. Nothing was changed on your account."
        points={PITCH}
        title="Sign-in failed"
        subtitle="Google sign-in didn't complete. Please try again."
        footer={
          <>
            <Link to="/login" className={heroLinkClass}>
              Back to login
            </Link>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <AlertBanner message={error} tone="hero" />
          <Link to="/login" className={`text-center text-sm ${heroLinkClass}`}>
            Back to login
          </Link>
        </div>
      </AuthHero>
    );
  }

  return (
    <AuthHero
      eyebrow="Google sign-in"
      headline="Signing you in"
      lead="Confirming your Google session, then taking you to your dashboard."
      points={PITCH}
      title="Signing you in…"
      subtitle="This usually takes a few seconds."
    >
      <div className="flex justify-center py-4">
        <div
          role="status"
          aria-label="Signing you in"
          className="h-8 w-8 animate-spin rounded-full border-2 border-white/15 border-t-gt-electric"
        />
      </div>
    </AuthHero>
  );
}
