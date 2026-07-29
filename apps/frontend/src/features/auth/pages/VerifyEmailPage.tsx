import { MailCheck } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { OtpInput } from "../components/OtpInput";
import { SuccessScreen } from "../components/SuccessScreen";
import { useResendOtp, useVerifyEmail } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import type { UserRole } from "../api/authApi";

const OTP_VALIDITY_SECONDS = 600;

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const role = (searchParams.get("role") as UserRole | null) ?? "candidate";

  const verifyEmail = useVerifyEmail();
  const resendOtp = useResendOtp();
  const [error, setError] = useState<string | null>(null);
  const [resendNotice, setResendNotice] = useState<string | null>(null);

  const handleComplete = (otp: string) => {
    setError(null);
    verifyEmail.mutate(
      { email, otp },
      { onError: (err) => setError(getAuthErrorMessage(err, "Invalid or expired code. Please try again.")) },
    );
  };

  const handleResend = () => {
    setError(null);
    setResendNotice(null);
    resendOtp.mutate(email, {
      onSuccess: () => setResendNotice("A new code is on its way."),
      onError: (err) => setError(getAuthErrorMessage(err)),
    });
  };

  if (!email) {
    return (
      <AuthLayout title="Verify your email">
        <AlertBanner message="Missing email address. Please sign up again." />
      </AuthLayout>
    );
  }

  if (verifyEmail.isSuccess) {
    return (
      <AuthLayout title="Email verified">
        <SuccessScreen title="You're all set" description="Your email has been verified successfully.">
          <Link
            to={`/login/${role}`}
            className="mt-2 rounded-xl bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110"
          >
            Continue to login
          </Link>
        </SuccessScreen>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Verify your email"
      subtitle={
        <>
          We sent a 6-digit code to <span className="font-medium text-slate-700">{email}</span>
        </>
      }
    >
      <div className="flex flex-col items-center gap-5">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
          <MailCheck size={22} />
        </div>

        {error ? <AlertBanner message={error} /> : null}
        {resendNotice && !error ? (
          <p className="text-sm text-emerald-600" role="status">
            {resendNotice}
          </p>
        ) : null}

        <OtpInput
          onComplete={handleComplete}
          onResend={handleResend}
          resendCooldownSeconds={OTP_VALIDITY_SECONDS > 60 ? 60 : OTP_VALIDITY_SECONDS}
          isResending={resendOtp.isPending}
          disabled={verifyEmail.isPending}
        />

        {verifyEmail.isPending ? <p className="text-sm text-slate-400">Verifying…</p> : null}
      </div>
    </AuthLayout>
  );
}
