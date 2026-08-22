import { z } from "zod";

/** Mirrors the backend's password policy in src/domains/auth/schemas.py — UX only, the server is authoritative. */
export const passwordSchema = z
  .string()
  .min(8, "Must be at least 8 characters")
  .max(128, "Must be at most 128 characters")
  .regex(/[A-Z]/, "Include at least one uppercase letter")
  .regex(/[a-z]/, "Include at least one lowercase letter")
  .regex(/\d/, "Include at least one number")
  .regex(/[^\w\s]/, "Include at least one special character");

const emailSchema = z.string().trim().min(1, "Email is required").email("Enter a valid email address");

const acceptTermsSchema = z
  .boolean()
  .refine((v) => v === true, { message: "You must accept the Terms & Conditions" });

/**
 * Student signup: email and password.
 *
 * Mirrors `CandidateRegisterRequest` — see that schema for why the other
 * fields moved. In short: every field on a signup form is a place to abandon
 * it, and a student arriving from the landing page has not been shown enough
 * yet to justify six of them. Name and phone are collected in the first
 * onboarding section, where they have visible context.
 *
 * No `confirm_password`. Retyping a password catches a typo the user cannot
 * see, so the redesigned form solves the actual problem instead — a reveal
 * toggle plus live strength feedback, which lets them *look* at what they
 * typed. Recruiter signup keeps the confirm field, because that form is
 * longer and its password is further from the submit button.
 *
 * CAPTCHA is intentionally disabled for this flow.
 */
export const candidateSignupSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
});

export type CandidateSignupFormValues = z.infer<typeof candidateSignupSchema>;

export const recruiterSignupSchema = z
  .object({
    full_name: z.string().trim().min(2, "Enter your full name").max(200),
    company_name: z.string().trim().min(2, "Enter your company name").max(200),
    company_email: emailSchema,
    password: passwordSchema,
    confirm_password: z.string(),
    accept_terms: acceptTermsSchema,
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

export type RecruiterSignupFormValues = z.infer<typeof recruiterSignupSchema>;

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Password is required"),
  remember_me: z.boolean(),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const forgotPasswordSchema = z.object({
  email: emailSchema,
});

export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    new_password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;
