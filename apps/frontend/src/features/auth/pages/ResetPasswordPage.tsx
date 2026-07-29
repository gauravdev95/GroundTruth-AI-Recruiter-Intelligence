import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { PasswordInput } from "../components/PasswordInput";
import { SuccessScreen } from "../components/SuccessScreen";
import { useResetPassword } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { resetPasswordSchema, type ResetPasswordFormValues } from "../schemas/authSchemas";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const resetPassword = useResetPassword();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    resetPassword.mutate(
      { token, newPassword: values.new_password, confirmPassword: values.confirm_password },
      { onError: (error) => setFormError(getAuthErrorMessage(error, "This link is invalid or has expired.")) },
    );
  });

  if (!token) {
    return (
      <AuthLayout title="Invalid link">
        <AlertBanner message="This password reset link is missing or malformed. Please request a new one." />
      </AuthLayout>
    );
  }

  if (resetPassword.isSuccess) {
    return (
      <AuthLayout title="Password updated">
        <SuccessScreen title="All set" description="Your password has been reset. You can now log in.">
          <Link
            to="/login/candidate"
            className="mt-2 rounded-xl bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110"
          >
            Go to login
          </Link>
        </SuccessScreen>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Reset your password" subtitle="Choose a new password for your account.">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError ? <AlertBanner message={formError} /> : null}

        <PasswordInput
          label="New password"
          autoComplete="new-password"
          placeholder="••••••••"
          showStrengthMeter
          error={errors.new_password?.message}
          {...register("new_password")}
          value={watch("new_password")}
        />

        <PasswordInput
          label="Confirm new password"
          autoComplete="new-password"
          placeholder="••••••••"
          error={errors.confirm_password?.message}
          {...register("confirm_password")}
        />

        <button
          type="submit"
          disabled={resetPassword.isPending}
          className="mt-1 flex items-center justify-center rounded-xl bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {resetPassword.isPending ? "Updating…" : "Reset password"}
        </button>
      </form>
    </AuthLayout>
  );
}
