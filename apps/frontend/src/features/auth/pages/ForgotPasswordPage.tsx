import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { FormField } from "../components/FormField";
import { SuccessScreen } from "../components/SuccessScreen";
import { useForgotPassword } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { forgotPasswordSchema, type ForgotPasswordFormValues } from "../schemas/authSchemas";

export function ForgotPasswordPage() {
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
            to="/login"
            className="mt-2 rounded bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-hover"
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
        <Link to="/login" className="font-medium text-ink underline decoration-rule underline-offset-2 transition hover:decoration-ink">
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
          className="mt-1 flex items-center justify-center rounded bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {forgotPassword.isPending ? "Sending…" : "Send reset link"}
        </button>
      </form>
    </AuthLayout>
  );
}
