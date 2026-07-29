import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { FormField } from "../components/FormField";
import { SuccessScreen } from "../components/SuccessScreen";
import { useForgotPassword } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { forgotPasswordSchema, type ForgotPasswordFormValues } from "../schemas/authSchemas";
import type { UserRole } from "../api/authApi";

export function ForgotPasswordPage() {
  const [searchParams] = useSearchParams();
  const role = (searchParams.get("role") as UserRole | null) ?? "candidate";
  const forgotPassword = useForgotPassword();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    forgotPassword.mutate(values.email, {
      onError: (error) => setFormError(getAuthErrorMessage(error)),
    });
  });

  if (forgotPassword.isSuccess) {
    return (
      <AuthLayout title="Check your inbox">
        <SuccessScreen
          title="Reset link sent"
          description="If an account with that email exists, we've sent a link to reset your password."
        >
          <Link
            to={`/login/${role}`}
            className="mt-2 rounded-xl bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110"
          >
            Back to login
          </Link>
        </SuccessScreen>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      subtitle="Enter your email and we'll send you a reset link."
      footer={
        <Link to={`/login/${role}`} className="font-medium text-indigo-600 hover:text-indigo-500">
          Back to login
        </Link>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError ? <AlertBanner message={formError} /> : null}

        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register("email")}
        />

        <button
          type="submit"
          disabled={forgotPassword.isPending}
          className="mt-1 flex items-center justify-center rounded-xl bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {forgotPassword.isPending ? "Sending…" : "Send reset link"}
        </button>
      </form>
    </AuthLayout>
  );
}
