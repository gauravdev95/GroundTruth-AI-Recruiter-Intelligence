import { zodResolver } from "@hookform/resolvers/zod";
import { isAxiosError } from "axios";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { CaptchaWidget } from "../components/CaptchaWidget";
import { Checkbox } from "../components/Checkbox";
import { FormField } from "../components/FormField";
import { GoogleButton } from "../components/GoogleButton";
import { PasswordInput } from "../components/PasswordInput";
import { useLogin } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { loginSchema, type LoginFormValues } from "../schemas/authSchemas";

export function RecruiterLoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [formError, setFormError] = useState<string | null>(null);

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
    login.mutate(
      { ...values, expected_role: "recruiter" },
      {
        onSuccess: () => navigate("/"),
        onError: (error) => {
          if (isAxiosError(error) && (error.response?.data as { code?: string } | undefined)?.code === "EMAIL_NOT_VERIFIED") {
            navigate(`/verify-email?email=${encodeURIComponent(values.email)}&role=recruiter`);
            return;
          }
          setFormError(getAuthErrorMessage(error));
        },
      },
    );
  });

  return (
    <AuthLayout
      title="Recruiter sign in"
      subtitle="Find engineering talent backed by evidence."
      footer={
        <>
          Don&rsquo;t have a company account?{" "}
          <Link to="/signup/recruiter" className="font-medium text-indigo-600 hover:text-indigo-500">
            Register your company
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError ? <AlertBanner message={formError} /> : null}

        <FormField
          label="Work email"
          type="email"
          autoComplete="email"
          placeholder="you@company.com"
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
          <Link to="/forgot-password?role=recruiter" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
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
          className="mt-1 flex items-center justify-center rounded-xl bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>

        <div className="my-1 flex items-center gap-3 text-xs text-slate-400">
          <div className="h-px flex-1 bg-slate-200" />
          OR
          <div className="h-px flex-1 bg-slate-200" />
        </div>

        <GoogleButton role="recruiter" />
      </form>
    </AuthLayout>
  );
}
