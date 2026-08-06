import { lazy } from "react";
import { Navigate, Route } from "react-router-dom";

/**
 * Every auth page is code-split.
 *
 * These were static imports, which put nine form pages — plus react-hook-form,
 * zod and the resolver bridge — into the entry chunk that the landing route has
 * to download before it can paint. Nobody arriving at `/` needs the reset-password
 * form. One `<Suspense>` boundary around the root `<Routes>` in App.tsx covers
 * all of them.
 */
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const SignupPage = lazy(() => import("./pages/SignupPage").then((m) => ({ default: m.SignupPage })));
const ForgotPasswordPage = lazy(() =>
  import("./pages/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })),
);
const ResetPasswordPage = lazy(() =>
  import("./pages/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })),
);
const OAuthCallbackPage = lazy(() =>
  import("./pages/OAuthCallbackPage").then((m) => ({ default: m.OAuthCallbackPage })),
);
const ForbiddenPage = lazy(() =>
  import("./pages/ForbiddenPage").then((m) => ({ default: m.ForbiddenPage })),
);

/** Spread directly inside the root <Routes> in App.tsx. */
export const authRoutes = (
  <>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/signup" element={<SignupPage />} />

    {/*
      The four role-split pages these replaced were live long enough to be
      bookmarked and to appear in verification emails already sent, so they
      redirect rather than 404. Sign-in no longer needs a role at all; sign-up
      still does, and carries it through as a query parameter so the merged
      page opens on the lane the old URL named.
    */}
    <Route path="/login/candidate" element={<Navigate to="/login" replace />} />
    <Route path="/login/recruiter" element={<Navigate to="/login" replace />} />
    <Route path="/signup/candidate" element={<Navigate to="/signup" replace />} />
    <Route path="/signup/recruiter" element={<Navigate to="/signup?role=recruiter" replace />} />

    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
    <Route path="/reset-password" element={<ResetPasswordPage />} />

    {/*
      `/verify-email` is gone with the OTP flow. It redirects rather than 404s
      for the same reason the role-split URLs above do: it was live long enough
      to appear in verification emails that have already been sent, and those
      recipients now have accounts that simply work. `/login` is where that
      link should land them.
    */}
    <Route path="/verify-email" element={<Navigate to="/login" replace />} />

    <Route path="/auth/callback" element={<OAuthCallbackPage />} />
    <Route path="/403" element={<ForbiddenPage />} />
  </>
);
