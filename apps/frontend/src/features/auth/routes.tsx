import { Route } from "react-router-dom";

import { CandidateLoginPage } from "./pages/CandidateLoginPage";
import { CandidateSignupPage } from "./pages/CandidateSignupPage";
import { ForbiddenPage } from "./pages/ForbiddenPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { OAuthCallbackPage } from "./pages/OAuthCallbackPage";
import { RecruiterLoginPage } from "./pages/RecruiterLoginPage";
import { RecruiterSignupPage } from "./pages/RecruiterSignupPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

/** Spread directly inside the root <Routes> in App.tsx. */
export const authRoutes = (
  <>
    <Route path="/login/candidate" element={<CandidateLoginPage />} />
    <Route path="/signup/candidate" element={<CandidateSignupPage />} />
    <Route path="/login/recruiter" element={<RecruiterLoginPage />} />
    <Route path="/signup/recruiter" element={<RecruiterSignupPage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
    <Route path="/reset-password" element={<ResetPasswordPage />} />
    <Route path="/verify-email" element={<VerifyEmailPage />} />
    <Route path="/auth/callback" element={<OAuthCallbackPage />} />
    <Route path="/403" element={<ForbiddenPage />} />
  </>
);
