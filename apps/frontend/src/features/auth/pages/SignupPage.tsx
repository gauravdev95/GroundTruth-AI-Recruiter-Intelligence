import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { AlertBanner } from "../components/AlertBanner";
import { AuthLayout } from "../components/AuthLayout";
import { CaptchaWidget } from "../components/CaptchaWidget";
import { Checkbox } from "../components/Checkbox";
import { FormField } from "../components/FormField";
import { GoogleButton } from "../components/GoogleButton";
import { PasswordInput } from "../components/PasswordInput";
import { useCandidateRegister, useRecruiterRegister } from "../hooks/useAuth";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import {
  candidateSignupSchema,
  recruiterSignupSchema,
  type CandidateSignupFormValues,
  type RecruiterSignupFormValues,
} from "../schemas/authSchemas";

type SignupRole = "student" | "recruiter";

/** Accepts the legacy `candidate` spelling so a redirected `/signup/candidate`
 * bookmark still preselects the right lane. */
function parseRole(raw: string | null): SignupRole {
  return raw === "recruiter" ? "recruiter" : "student";
}

const termsCheckboxLabel = (
  <>
    I agree to the{" "}
    <a
      href="/terms"
      className="font-medium text-ink underline decoration-rule underline-offset-2 transition hover:decoration-ink"
    >
      Terms &amp; Conditions
    </a>
  </>
);

const submitButtonClass =
  "mt-1 flex items-center justify-center rounded bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-hover disabled:cursor-not-allowed disabled:opacity-60";

function Divider() {
  return (
    <div className="my-1 flex items-center gap-3 text-xs text-slate-400">
      <div className="h-px flex-1 bg-slate-200" />
      OR
      <div className="h-px flex-1 bg-slate-200" />
    </div>
  );
}

/**
 * The role switch. Rendered as a radiogroup rather than a link pair so the
 * choice is visibly part of the form — the role is a field of the account
 * being created, and it is immutable afterwards, which a pair of tabs that
 * look like navigation would understate.
 */
function RoleToggle({ value, onChange }: { value: SignupRole; onChange: (role: SignupRole) => void }) {
  const options: { role: SignupRole; label: string; hint: string }[] = [
    { role: "student", label: "I'm a student", hint: "Build an evidence-backed profile" },
    { role: "recruiter", label: "I'm a recruiter", hint: "Hire on verified evidence" },
  ];

  return (
    <div role="radiogroup" aria-label="Account type" className="grid gap-2 sm:grid-cols-2">
      {options.map((option) => {
        const isSelected = option.role === value;
        return (
          <button
            key={option.role}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => onChange(option.role)}
            className={`rounded-xl border px-4 py-3 text-left transition ${
              isSelected
                ? "border-ink bg-ink/[0.03] ring-1 ring-ink"
                : "border-slate-300 bg-white hover:border-slate-400"
            }`}
          >
            <span className="block text-sm font-semibold text-ink">{option.label}</span>
            <span className="mt-0.5 block text-xs text-slate-500">{option.hint}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * Each lane gets its own component, and therefore its own `useForm`, because
 * the two forms genuinely differ: a student registers with a personal email
 * and phone number, a recruiter with a company name and company email, against
 * two different endpoints. One form with conditional fields would have to
 * carry a union-typed resolver and clear stale values on every toggle; two
 * forms behind a switch simply cannot leak one lane's input into the other.
 */
function StudentSignupForm() {
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
      onSuccess: (data) => navigate(`/verify-email?email=${encodeURIComponent(data.email)}`),
      onError: (error) => setFormError(getAuthErrorMessage(error)),
    });
  });

  return (
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

      <Checkbox label={termsCheckboxLabel} error={errors.accept_terms?.message} {...register("accept_terms")} />

      <button type="submit" disabled={register_.isPending} className={submitButtonClass}>
        {register_.isPending ? "Creating account…" : "Create account"}
      </button>

      <Divider />

      <GoogleButton role="candidate" label="Sign up with Google" />
    </form>
  );
}

function RecruiterSignupForm() {
  const navigate = useNavigate();
  const register_ = useRecruiterRegister();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<RecruiterSignupFormValues>({
    resolver: zodResolver(recruiterSignupSchema),
    defaultValues: {
      full_name: "",
      company_name: "",
      company_email: "",
      password: "",
      confirm_password: "",
      captcha_token: "",
      accept_terms: false,
    },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    register_.mutate(values, {
      onSuccess: (data) => navigate(`/verify-email?email=${encodeURIComponent(data.email)}`),
      onError: (error) => setFormError(getAuthErrorMessage(error)),
    });
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {formError ? <AlertBanner message={formError} /> : null}

      <FormField
        label="Full name"
        autoComplete="name"
        placeholder="Grace Hopper"
        error={errors.full_name?.message}
        {...register("full_name")}
      />

      <FormField
        label="Company name"
        autoComplete="organization"
        placeholder="Acme Corp"
        error={errors.company_name?.message}
        {...register("company_name")}
      />

      <FormField
        label="Company email"
        type="email"
        autoComplete="email"
        placeholder="you@company.com"
        error={errors.company_email?.message}
        {...register("company_email")}
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

      <Checkbox label={termsCheckboxLabel} error={errors.accept_terms?.message} {...register("accept_terms")} />

      <button type="submit" disabled={register_.isPending} className={submitButtonClass}>
        {register_.isPending ? "Creating account…" : "Create account"}
      </button>

      <Divider />

      <GoogleButton role="recruiter" label="Sign up with Google" />
    </form>
  );
}

/**
 * The single registration entry point, replacing `/signup/candidate` and
 * `/signup/recruiter`. The role is chosen in-form and is fixed on the account
 * from then on, which is why it is a field here rather than two separate URLs
 * a user could land on without ever making a deliberate choice.
 */
export function SignupPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const role = parseRole(searchParams.get("role"));

  function selectRole(next: SignupRole) {
    // Mirrored into the URL so the choice survives a refresh and stays
    // shareable, and `replace` so toggling doesn't stack history entries.
    setSearchParams(next === "student" ? {} : { role: next }, { replace: true });
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle={
        role === "student"
          ? "Turn your GitHub work into an evidence-backed profile."
          : "Search evidence-backed engineering talent."
      }
      footer={
        <>
          Already have an account?{" "}
          <Link
            to="/login"
            className="font-medium text-ink underline decoration-rule underline-offset-2 transition hover:decoration-ink"
          >
            Log in
          </Link>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        <RoleToggle value={role} onChange={selectRole} />
        {role === "student" ? <StudentSignupForm /> : <RecruiterSignupForm />}
      </div>
    </AuthLayout>
  );
}
