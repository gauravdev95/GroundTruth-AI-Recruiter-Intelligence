import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthHero, heroLinkClass } from "../components/AuthHero";
import { HeroSubmit } from "../components/HeroSubmit";
import { PasswordInput } from "../components/PasswordInput";
import { SuccessScreen } from "../components/SuccessScreen";
import { useResetPassword } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { resetPasswordSchema, type ResetPasswordFormValues } from "../schemas/authSchemas";

const PITCH = [
  "Your new password protects the profile your work built.",
  "Make it unique — don't reuse one from another site.",
  "Once saved, log in with it right away.",
] as const;

const HERO_LOGIN_LINK_CLASS =
  "mt-2 inline-flex items-center justify-center gap-2 rounded-lg bg-gt-electric px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#1D4FD8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70";

/**
 * Password reset, on the same split-screen hero as sign-in and sign-up.
 *
 * Phase 3 moved this off the quiet `AuthLayout` card for the same reason as
 * the forgot-password page: the recovery flow kept leaving the product's
 * visual world and coming back. The token handling, schema and submission
 * are unchanged — only the shell and the field tone moved.
 */
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

  const shell = (title: string, subtitle: string, eyebrow: string, headline: string, lead: string) => ({
    eyebrow,
    headline,
    lead,
    points: PITCH,
    title,
    subtitle,
  });

  if (!token) {
    return (
      <AuthHero
        {...shell(
          "Invalid link",
          "Request a new reset link from the login page.",
          "Account recovery",
          "That link doesn't work",
          "Reset links are single-use. Request a fresh one and try again.",
        )}
        footer={
          <>
            <Link to="/forgot-password" className={heroLinkClass}>
              Request a new link
            </Link>
            {" · "}
            <Link to="/login" className={heroLinkClass}>
              Back to login
            </Link>
          </>
        }
      >
        <AlertBanner
          tone="hero"
          message="This password reset link is missing or malformed. Please request a new one."
        />
      </AuthHero>
    );
  }

  if (resetPassword.isSuccess) {
    return (
      <AuthHero
        {...shell(
          "Password updated",
          "Your password has been reset. You can now log in.",
          "Account recovery",
          "All set",
          "Your new password is saved. Log in with it whenever you're ready.",
        )}
        footer={
          <>
            <Link to="/login" className={heroLinkClass}>
              Back to login
            </Link>
          </>
        }
      >
        <SuccessScreen
          tone="hero"
          title="All set"
          description="Your password has been reset. You can now log in."
        >
          <Link to="/login" className={HERO_LOGIN_LINK_CLASS}>
            Go to login
          </Link>
        </SuccessScreen>
      </AuthHero>
    );
  }

  return (
    <AuthHero
      {...shell(
        "Reset your password",
        "Choose a new password for your account.",
        "Account recovery",
        "Choose a new password",
        "Pick something only you know. The strength meter is there to help, not to judge.",
      )}
      footer={
        <>
          <Link to="/login" className={heroLinkClass}>
            Back to login
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError ? <AlertBanner message={formError} tone="hero" /> : null}

        <PasswordInput
          label="New password"
          tone="hero"
          autoComplete="new-password"
          placeholder="••••••••"
          showStrengthMeter
          error={errors.new_password?.message}
          {...register("new_password")}
          value={watch("new_password")}
        />

        <PasswordInput
          label="Confirm new password"
          tone="hero"
          autoComplete="new-password"
          placeholder="••••••••"
          error={errors.confirm_password?.message}
          {...register("confirm_password")}
        />

        <HeroSubmit pending={resetPassword.isPending} pendingLabel="Updating…">
          Reset password
        </HeroSubmit>
      </form>
    </AuthHero>
  );
}
