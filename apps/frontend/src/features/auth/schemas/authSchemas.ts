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

const phoneSchema = z
  .string()
  .trim()
  .min(1, "Phone number is required")
  .transform((v) => v.replace(/[\s-]/g, ""))
  .refine((v) => /^\+?[1-9]\d{7,14}$/.test(v), "Enter a valid phone number");

const emailSchema = z.string().trim().min(1, "Email is required").email("Enter a valid email address");

const acceptTermsSchema = z
  .boolean()
  .refine((v) => v === true, { message: "You must accept the Terms & Conditions" });

const captchaSchema = z.string().min(1, "Please complete the CAPTCHA");

export const candidateSignupSchema = z
  .object({
    full_name: z.string().trim().min(2, "Enter your full name").max(200),
    email: emailSchema,
    phone_number: phoneSchema,
    password: passwordSchema,
    confirm_password: z.string(),
    captcha_token: captchaSchema,
    accept_terms: acceptTermsSchema,
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

export type CandidateSignupFormValues = z.infer<typeof candidateSignupSchema>;

export const recruiterSignupSchema = z
  .object({
    full_name: z.string().trim().min(2, "Enter your full name").max(200),
    company_name: z.string().trim().min(2, "Enter your company name").max(200),
    company_email: emailSchema,
    password: passwordSchema,
    confirm_password: z.string(),
    captcha_token: captchaSchema,
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
  captcha_token: captchaSchema,
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
