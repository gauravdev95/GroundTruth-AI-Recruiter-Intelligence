import { zodResolver } from "@hookform/resolvers/zod";
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
import { useCandidateRegister } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { candidateSignupSchema, type CandidateSignupFormValues } from "../schemas/authSchemas";

export function CandidateSignupPage() {
  const navigate = useNavigate();
  const register_ = useCandidateRegister();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<CandidateSignupFormValues>({
    resolver: zodResolver(candidateSignupSchema),
    defaultValues: {
      full_name: "",
      email: "",
      phone_number: "",
      password: "",
      confirm_password: "",
      captcha_token: "",
      accept_terms: false,
    },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    register_.mutate(values, {
      onSuccess: (data) => navigate(`/verify-email?email=${encodeURIComponent(data.email)}&role=candidate`),
      onError: (error) => setFormError(getAuthErrorMessage(error)),
    });
  });

  return (
    <AuthLayout
      title="Create your candidate account"
      subtitle="Turn your GitHub work into an evidence-backed profile."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login/candidate" className="font-medium text-indigo-600 hover:text-indigo-500">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError ? <AlertBanner message={formError} /> : null}

        <FormField
          label="Full name"
          autoComplete="name"
          placeholder="Ada Lovelace"
          error={errors.full_name?.message}
          {...register("full_name")}
        />

        <FormField
          label="Email address"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register("email")}
        />

        <FormField
          label="Mobile number"
          type="tel"
          autoComplete="tel"
          placeholder="+1 415 555 2671"
          error={errors.phone_number?.message}
          {...register("phone_number")}
        />

        <PasswordInput
          label="Password"
          autoComplete="new-password"
          placeholder="••••••••"
          showStrengthMeter
          error={errors.password?.message}
          {...register("password")}
          value={watch("password")}
        />

        <PasswordInput
          label="Confirm password"
          autoComplete="new-password"
          placeholder="••••••••"
          error={errors.confirm_password?.message}
          {...register("confirm_password")}
        />

        <CaptchaWidget
          error={errors.captcha_token?.message}
          onChange={(token) => setValue("captcha_token", token ?? "", { shouldValidate: true })}
        />

        <Checkbox
          label={
            <>
              I agree to the{" "}
              <a href="/terms" className="font-medium text-indigo-600 hover:text-indigo-500">
                Terms &amp; Conditions
              </a>
            </>
          }
          error={errors.accept_terms?.message}
          {...register("accept_terms")}
        />

        <button
          type="submit"
          disabled={register_.isPending}
          className="mt-1 flex items-center justify-center rounded-xl bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {register_.isPending ? "Creating account…" : "Create account"}
        </button>

        <div className="my-1 flex items-center gap-3 text-xs text-slate-400">
          <div className="h-px flex-1 bg-slate-200" />
          OR
          <div className="h-px flex-1 bg-slate-200" />
        </div>

        <GoogleButton role="candidate" label="Sign up with Google" />
      </form>
    </AuthLayout>
  );
}
