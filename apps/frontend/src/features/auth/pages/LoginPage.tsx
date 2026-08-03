import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { CaptchaWidget } from "../components/CaptchaWidget";
import { Checkbox } from "../components/Checkbox";
import { FormField } from "../components/FormField";
import { GoogleButton } from "../components/GoogleButton";
import { PasswordInput } from "../components/PasswordInput";
import { useLogin } from "../hooks/useAuth";
import { dashboardPathForRole } from "../lib/dashboardPath";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { loginSchema, type LoginFormValues } from "../schemas/authSchemas";

/**
 * The single sign-in entry point, replacing the separate `/login/candidate`
 * and `/login/recruiter` pages.
 *
 * Nothing here declares a role. The two old pages each sent `expected_role`
 * and the server rejected a mismatch, which meant a recruiter who clicked the
 * wrong "Login" button on the landing page was told their own credentials were
 * for the other lane — a distinction the user has no reason to think about at
 * sign-in. The role is now read off the session the server issues, and decides
 * only where to land.
 */
export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const [formError, setFormError] = useState<string | null>(null);

  // Set by `ProtectedRoute` when it bounces an unauthenticated user off a
  // deep link. Only same-origin absolute paths are honoured — an attacker who
  // can seed router state must not be able to turn this into an open redirect.
  const requestedPath = (location.state as { from?: string } | null)?.from;
  const returnTo =
    requestedPath && requestedPath.startsWith("/") && !requestedPath.startsWith("//")
      ? requestedPath
      : null;

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", captcha_token: "", remember_me: false },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    login.mutate(values, {
      onSuccess: (data) =>
        navigate(returnTo ?? dashboardPathForRole(data.user.role), { replace: true }),
      onError: (error) => {
        if (
          isAxiosError(error) &&
          (error.response?.data as { code?: string } | undefined)?.code === "EMAIL_NOT_VERIFIED"
        ) {
          navigate(`/verify-email?email=${encodeURIComponent(values.email)}`);
          return;
        }
        setFormError(getAuthErrorMessage(error));
      },
    });
  });

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Log in to GroundTruth."
      footer={
        <>
          New to GroundTruth?{" "}
          <Link
            to="/signup"
            className="font-medium text-ink underline decoration-rule underline-offset-2 transition hover:decoration-ink"
          >
            Create an account
          </Link>
        </>
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

        <PasswordInput
          label="Password"
          autoComplete="current-password"
          placeholder="••••••••"
          error={errors.password?.message}
          {...register("password")}
        />

        <div className="flex items-center justify-between">
          <Checkbox label="Remember me" {...register("remember_me")} />
          <Link
            to="/forgot-password"
            className="text-sm font-medium text-ink underline decoration-rule underline-offset-2 transition hover:decoration-ink"
          >
            Forgot password?
          </Link>
        </div>

        <CaptchaWidget
          error={errors.captcha_token?.message}
          onChange={(token) => setValue("captcha_token", token ?? "", { shouldValidate: true })}
        />

        <button
          type="submit"
          disabled={login.isPending}
          className="mt-1 flex items-center justify-center rounded bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {login.isPending ? "Logging in…" : "Log in"}
        </button>

        {/*
          Google sign-in still needs a role: OAuth creates the account on first
          use, and the server cannot infer which kind to create. Existing users
          are unaffected — the role on the account wins over the one in the
          link — so this only decides the lane for a brand-new Google account.
        */}
        <div className="my-1 flex items-center gap-3 text-xs text-slate-400">
          <div className="h-px flex-1 bg-slate-200" />
          OR
          <div className="h-px flex-1 bg-slate-200" />
        </div>

        <GoogleButton role="candidate" label="Continue with Google as a student" />
        <GoogleButton role="recruiter" label="Continue with Google as a recruiter" />
      </form>
    </AuthLayout>
  );
}
