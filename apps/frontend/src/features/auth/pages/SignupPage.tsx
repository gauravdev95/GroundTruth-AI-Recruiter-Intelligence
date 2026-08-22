import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { DURATION, EASE, SPRING_TRAVEL, STAGGER, TRAVEL, useReducedMotionSafe } from "@/design/motion";
import { Shake } from "@/design/primitives";

import { AlertBanner } from "../components/AlertBanner";
import { AuthHero, heroLinkClass } from "../components/AuthHero";
import { Checkbox } from "../components/Checkbox";
import { FormField } from "../components/FormField";
import { GoogleButton } from "../components/GoogleButton";
import { HeroSubmit } from "../components/HeroSubmit";
import { PasswordInput } from "../components/PasswordInput";
import { useCandidateRegister, useRecruiterRegister } from "../hooks/useAuth";
import { dashboardPathForRole } from "../lib/dashboardPath";
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

const PITCH: Record<SignupRole, readonly string[]> = {
  student: [
    "Connect GitHub once; the profile builds itself from your commits.",
    "Skills are backed by the repositories that demonstrate them.",
    "Recruiters search the evidence, so your work does the pitching.",
  ],
  recruiter: [
    "Search candidates by what they have built, not what they typed.",
    "Every claim on a profile links to the artefact behind it.",
    "Shortlist from evidence before the first conversation.",
  ],
};

const termsLine = (
  <>
    By continuing you agree to the{" "}
    <a href="/terms" className={heroLinkClass}>
      Terms &amp; Conditions
    </a>
  </>
);

const termsCheckboxLabel = (
  <>
    I agree to the{" "}
    <a href="/terms" className={heroLinkClass}>
      Terms &amp; Conditions
    </a>
  </>
);

function Divider() {
  return (
    <div className="my-1 flex items-center gap-3 text-xs uppercase tracking-widest text-white/35">
      <div className="h-px flex-1 bg-white/12" />
      or
      <div className="h-px flex-1 bg-white/12" />
    </div>
  );
}

/**
 * Field entrance for the nth control. Staggered top-to-bottom, which is also
 * tab order, and offset so fields arrive after the panel has settled rather
 * than sliding in while their own container is still moving.
 */
function useFieldEntrance() {
  const reduced = useReducedMotionSafe();

  return (index: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: TRAVEL },
          animate: { opacity: 1, y: 0 },
          transition: {
            duration: DURATION.base,
            ease: EASE.entrance,
            delay: DURATION.fast + index * STAGGER.siblings,
          },
        };
}

/**
 * The role switch. Rendered as a radiogroup rather than a link pair so the
 * choice is visibly part of the form — the role is a field of the account
 * being created, and it is immutable afterwards, which a pair of tabs that
 * look like navigation would understate.
 *
 * The selected state is a shared `layoutId` pill rather than a class swap, so
 * the highlight *travels* between the two options. That is `orient` motion in
 * the `PURPOSE` taxonomy: it shows the choice moving from one to the other,
 * which a cross-fade cannot.
 */
function RoleToggle({ value, onChange }: { value: SignupRole; onChange: (role: SignupRole) => void }) {
  const reduced = useReducedMotionSafe();

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
            className="group relative rounded-xl px-4 py-3 text-left transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric/60"
          >
            {isSelected ? (
              <motion.span
                layoutId="signup-role-pill"
                aria-hidden="true"
                className="absolute inset-0 rounded-xl border border-gt-electric/60 bg-gt-electric/15"
                transition={reduced ? { duration: 0 } : SPRING_TRAVEL}
              />
            ) : (
              <span
                aria-hidden="true"
                className="absolute inset-0 rounded-xl border border-white/12 transition-colors duration-200 group-hover:border-white/28"
              />
            )}

            <span className="relative block text-sm font-semibold text-white">{option.label}</span>
            <span className="relative mt-0.5 block text-xs text-white/55">{option.hint}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * Each lane gets its own component, and therefore its own `useForm`, because
 * the two forms genuinely differ: a student registers with a personal email,
 * a recruiter with a company name and company email, against two different
 * endpoints. One form with conditional fields would have to carry a
 * union-typed resolver and clear stale values on every toggle; two forms
 * behind a switch simply cannot leak one lane's input into the other.
 *
 * BOTH SUBMIT STRAIGHT INTO THE PRODUCT. There is no verification step: the
 * register call creates the account, signs it in and returns a session, so the
 * success handler navigates to the dashboard. It used to navigate to
 * `/verify-email?email=…`, which no longer exists.
 */
function StudentSignupForm() {
  const navigate = useNavigate();
  const register_ = useCandidateRegister();
  const field = useFieldEntrance();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<CandidateSignupFormValues>({
    resolver: zodResolver(candidateSignupSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    register_.mutate(values, {
      onSuccess: (data) => navigate(dashboardPathForRole(data.user.role), { replace: true }),
      onError: (error) => setFormError(getAuthErrorMessage(error)),
    });
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Shake active={Boolean(formError)}>
        {formError ? <AlertBanner message={formError} tone="hero" /> : null}
      </Shake>

      <motion.div {...field(0)}>
        <FormField
          label="Email address"
          tone="hero"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register("email")}
        />
      </motion.div>

      {/*
        No confirm field. Retyping catches a typo the student cannot see, so
        the reveal toggle and strength meter solve the real problem — they
        let the student *look* at what they typed.
      */}
      <motion.div {...field(1)}>
        <PasswordInput
          label="Password"
          tone="hero"
          autoComplete="new-password"
          placeholder="••••••••"
          showStrengthMeter
          error={errors.password?.message}
          {...register("password")}
          value={watch("password")}
        />
      </motion.div>

      <motion.div {...field(2)}>
        <HeroSubmit pending={register_.isPending} pendingLabel="Creating account…">
          Create account
        </HeroSubmit>
      </motion.div>

      {/*
        Sign-in-wrap consent: the terms line sits directly under the control
        that performs the action, replacing the separate checkbox. This is a
        legal posture change, not just a layout one — see the note in the
        backend's `CandidateRegisterRequest`.
      */}
      <motion.div {...field(3)} className="flex flex-col gap-4">
        <p className="text-center text-xs leading-relaxed text-white/45">{termsLine}</p>
        <Divider />
        <GoogleButton role="candidate" tone="hero" label="Sign up with Google" />
      </motion.div>
    </form>
  );
}

function RecruiterSignupForm() {
  const navigate = useNavigate();
  const register_ = useRecruiterRegister();
  const field = useFieldEntrance();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
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
      accept_terms: false,
    },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    register_.mutate(values, {
      onSuccess: (data) => navigate(dashboardPathForRole(data.user.role), { replace: true }),
      onError: (error) => setFormError(getAuthErrorMessage(error)),
    });
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Shake active={Boolean(formError)}>
        {formError ? <AlertBanner message={formError} tone="hero" /> : null}
      </Shake>

      <motion.div {...field(0)} className="grid gap-4 sm:grid-cols-2">
        <FormField
          label="Full name"
          tone="hero"
          autoComplete="name"
          placeholder="Grace Hopper"
          error={errors.full_name?.message}
          {...register("full_name")}
        />
        <FormField
          label="Company name"
          tone="hero"
          autoComplete="organization"
          placeholder="Acme Corp"
          error={errors.company_name?.message}
          {...register("company_name")}
        />
      </motion.div>

      <motion.div {...field(1)}>
        <FormField
          label="Company email"
          tone="hero"
          type="email"
          autoComplete="email"
          placeholder="you@company.com"
          error={errors.company_email?.message}
          {...register("company_email")}
        />
      </motion.div>

      <motion.div {...field(2)}>
        <PasswordInput
          label="Password"
          tone="hero"
          autoComplete="new-password"
          placeholder="••••••••"
          showStrengthMeter
          error={errors.password?.message}
          {...register("password")}
          value={watch("password")}
        />
      </motion.div>

      <motion.div {...field(3)}>
        <PasswordInput
          label="Confirm password"
          tone="hero"
          autoComplete="new-password"
          placeholder="••••••••"
          error={errors.confirm_password?.message}
          {...register("confirm_password")}
        />
      </motion.div>

      <motion.div {...field(4)}>
        <Checkbox
          label={termsCheckboxLabel}
          tone="hero"
          error={errors.accept_terms?.message}
          {...register("accept_terms")}
        />
      </motion.div>

      <motion.div {...field(5)} className="flex flex-col gap-4">
        <HeroSubmit pending={register_.isPending} pendingLabel="Creating account…">
          Create account
        </HeroSubmit>
        <Divider />
        <GoogleButton role="recruiter" tone="hero" label="Sign up with Google" />
      </motion.div>
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
    <AuthHero
      eyebrow="Create your account"
      headline={role === "student" ? "Let the code speak" : "Hire on evidence"}
      lead={
        role === "student"
          ? "Turn the work you have already shipped into a profile a recruiter can verify."
          : "Search engineering talent by the artefacts behind the claims."
      }
      points={PITCH[role]}
      title="Create your account"
      subtitle={
        role === "student"
          ? "Two fields. The rest of your profile is built from your work."
          : "Set up your company workspace."
      }
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className={heroLinkClass}>
            Log in
          </Link>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        <RoleToggle value={role} onChange={selectRole} />
        {/*
          Keyed on the role so switching lanes remounts the form. That is what
          guarantees the other lane's values and validation errors are gone
          rather than merely hidden, and it re-runs the field entrance so the
          new form reads as having arrived.
        */}
        {role === "student" ? (
          <StudentSignupForm key="student" />
        ) : (
          <RecruiterSignupForm key="recruiter" />
        )}
      </div>
    </AuthHero>
  );
}
