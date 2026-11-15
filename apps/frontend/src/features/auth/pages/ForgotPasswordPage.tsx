import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthHero, heroLinkClass } from "../components/AuthHero";
import { FormField } from "../components/FormField";
import { HeroSubmit } from "../components/HeroSubmit";
import { SuccessScreen } from "../components/SuccessScreen";
import { useForgotPassword } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { forgotPasswordSchema, type ForgotPasswordFormValues } from "../schemas/authSchemas";

const PITCH = [
  "The reset link goes to the email on your account.",
  "Use it once, then choose a new password.",
  "Your evidence, matches and applications stay exactly as they were.",
] as const;

/**
 * Password recovery, on the same split-screen hero as sign-in and sign-up.
 *
 * Phase 3 moved this off the quiet `AuthLayout` card: "Forgot password?"
 * used to walk a visitor out of the product's visual world into a different
 * one, and back again on the next screen. The form, schema and submission
 * are unchanged — only the shell and the field tone moved.
 */
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
      <AuthHero
        eyebrow="Check your inbox"
        headline="Reset link sent"
        lead="If an account with that email exists, a reset link is on its way."
        points={PITCH}
        title="Check your inbox"
        subtitle="If an account with that email exists, we've sent a link to reset your password."
        footer={
          <>
            Remembered it?{" "}
            <Link to="/login" className={heroLinkClass}>
              Back to login
            </Link>
          </>
        }
      >
        <SuccessScreen
          tone="hero"
          title="Reset link sent"
          description="If an account with that email exists, we've sent a link to reset your password."
        >
          <Link
            to="/login"
            className="mt-2 inline-flex items-center justify-center gap-2 rounded-lg bg-gt-electric px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#1D4FD8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
          >
            Back to login
          </Link>
        </SuccessScreen>
      </AuthHero>
    );
  }

  return (
    <AuthHero
      eyebrow="Account recovery"
      headline="Reset your password"
      lead="One link, and you're back to the profile your work built."
      points={PITCH}
      title="Forgot your password?"
      subtitle="Enter your email and we'll send you a reset link."
      footer={
        <>
          Remembered it?{" "}
          <Link to="/login" className={heroLinkClass}>
            Back to login
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError ? <AlertBanner message={formError} tone="hero" /> : null}

        <FormField
          label="Email"
          tone="hero"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register("email")}
        />

        <HeroSubmit pending={forgotPassword.isPending} pendingLabel="Sending…">
          Send reset link
        </HeroSubmit>
      </form>
    </AuthHero>
  );
}
