import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { buttonVariants } from "@/components/buttonVariants";

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
            className={buttonVariants({ variant: "primary", size: "md", className: "mt-2" })}
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
        <Link to="/login" className="font-medium text-[var(--ink)] underline decoration-[var(--rule)] underline-offset-2 transition-colors hover:decoration-[var(--ink)]">
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
          className={buttonVariants({ variant: "primary", size: "md", className: "mt-1 w-full" })}
        >
          {forgotPassword.isPending ? "Sending…" : "Send reset link"}
        </button>
      </form>
    </AuthLayout>
  );
}
