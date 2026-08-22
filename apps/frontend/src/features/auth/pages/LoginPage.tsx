import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { DURATION, EASE, STAGGER, TRAVEL, useReducedMotionSafe } from "@/design/motion";
import { Shake } from "@/design/primitives";

import { AlertBanner } from "../components/AlertBanner";
import { AuthHero, heroLinkClass } from "../components/AuthHero";
import { Checkbox } from "../components/Checkbox";
import { FormField } from "../components/FormField";
import { GoogleButton } from "../components/GoogleButton";
import { HeroSubmit } from "../components/HeroSubmit";
import { PasswordInput } from "../components/PasswordInput";
import { TestCredentials } from "../components/TestCredentials";
import { useLogin } from "../hooks/useAuth";
import { dashboardPathForRole } from "../lib/dashboardPath";
import { getAuthErrorMessage } from "../lib/getErrorMessage";
import { loginSchema, type LoginFormValues } from "../schemas/authSchemas";

const PITCH = [
  "Every skill on a profile traces back to code someone actually wrote.",
  "Repositories, commits and contributions, checked — not self-reported.",
  "One profile, built once, readable by every recruiter on the platform.",
] as const;

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
 *
 * There is no `EMAIL_NOT_VERIFIED` branch any more. There used to be one that
 * redirected to `/verify-email`, and it never fired: it read `error.response
 * .data.code`, but the backend's envelope is `{error: {code}}` (see
 * `lib/apiError.ts`), so the property was always `undefined` and an unverified
 * user got a dead-end banner instead. Both the bug and the flow it guarded are
 * gone — nothing blocks a login on email verification.
 */
export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const reduced = useReducedMotionSafe();
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
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", remember_me: false },
  });

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    login.mutate(values, {
      onSuccess: (data) =>
        navigate(returnTo ?? dashboardPathForRole(data.user.role), { replace: true }),
      onError: (error) => setFormError(getAuthErrorMessage(error)),
    });
  });

  /** Field entrance. Staggered top-to-bottom, which is also tab order. */
  const field = (index: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: TRAVEL },
          animate: { opacity: 1, y: 0 },
          transition: {
            duration: DURATION.base,
            ease: EASE.entrance,
            // Offset so the fields arrive after the panel itself has settled,
            // rather than sliding in while their own container is still moving.
            delay: DURATION.fast + index * STAGGER.siblings,
          },
        };

  return (
    <AuthHero
      eyebrow="Welcome back"
      headline="Proof, not promises"
      lead="Sign in to the profile your work already earned you."
      points={PITCH}
      title="Log in"
      subtitle="Use the email you signed up with."
      footer={
        <>
          New to GroundTruth?{" "}
          <Link to="/signup" className={heroLinkClass}>
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {/*
          `Shake` is the product's `warn` primitive. It is keyed on the presence
          of a form-level error, so a second failed attempt with the same
          message still moves — the banner alone would be visually identical to
          the one already on screen and would look like nothing happened.
        */}
        <Shake active={Boolean(formError)}>
          {formError ? <AlertBanner message={formError} tone="hero" /> : null}
        </Shake>

        <motion.div {...field(0)}>
          <FormField
            label="Email"
            tone="hero"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            error={errors.email?.message}
            {...register("email")}
          />
        </motion.div>

        <motion.div {...field(1)}>
          <PasswordInput
            label="Password"
            tone="hero"
            autoComplete="current-password"
            placeholder="••••••••"
            error={errors.password?.message}
            {...register("password")}
          />
        </motion.div>

        <motion.div {...field(2)} className="flex items-center justify-between gap-4">
          <Checkbox label="Remember me" tone="hero" {...register("remember_me")} />
          <Link to="/forgot-password" className={`text-sm ${heroLinkClass}`}>
            Forgot password?
          </Link>
        </motion.div>

        <motion.div {...field(3)}>
          <HeroSubmit pending={login.isPending} pendingLabel="Logging in…">
            Log in
          </HeroSubmit>
        </motion.div>

        {/*
          Google sign-in still needs a role: OAuth creates the account on first
          use, and the server cannot infer which kind to create. Existing users
          are unaffected — the role on the account wins over the one in the
          link — so this only decides the lane for a brand-new Google account.
        */}
        <motion.div {...field(4)} className="flex flex-col gap-3">
          <div className="my-1 flex items-center gap-3 text-xs uppercase tracking-widest text-white/35">
            <div className="h-px flex-1 bg-white/12" />
            or
            <div className="h-px flex-1 bg-white/12" />
          </div>

          <GoogleButton role="candidate" tone="hero" label="Continue with Google as a student" />
          <GoogleButton role="recruiter" tone="hero" label="Continue with Google as a recruiter" />
        </motion.div>

        {/* Renders nothing outside a dev build, and is stripped from the
            production bundle entirely — see the component. */}
        <motion.div {...field(5)}>
          <TestCredentials />
        </motion.div>
      </form>
    </AuthHero>
  );
}
