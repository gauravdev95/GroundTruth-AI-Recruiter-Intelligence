import { z } from "zod";

/**
 * Mirrors `apps/backend/src/domains/student/schemas.py` for UX only — the
 * server revalidates everything and is authoritative. Keep the two in step:
 * a rule relaxed here but not there just moves the error from inline to a
 * toast.
 */

const MAX_PROJECTS = 3;
const MAX_TECHNOLOGIES = 15;

const MIN_GRADUATION_YEAR = 1970;
const MAX_GRADUATION_YEAR = 2100;

const degreeValues = [
  "btech",
  "be",
  "bsc",
  "bca",
  "mtech",
  "msc",
  "mca",
  "mba",
  "phd",
  "other",
] as const;

const branchValues = [
  "cse",
  "it",
  "ece",
  "eee",
  "mechanical",
  "civil",
  "chemical",
  "aiml",
  "data_science",
  "other",
] as const;

const targetRoleValues = [
  "backend",
  "frontend",
  "fullstack",
  "mobile",
  "data_engineer",
  "data_scientist",
  "ml_engineer",
  "devops",
  "qa",
  "security",
  "other",
] as const;

const platformValues = ["leetcode", "codeforces", "hackerrank"] as const;
const employmentTypeValues = ["internship", "freelance", "part_time"] as const;

/** Absolute http(s) only — matches the backend's scheme allow-list, which
 * exists so a background fetcher is never handed a `javascript:` URL. */
const httpUrlSchema = z
  .string()
  .trim()
  .max(500, "Must be at most 500 characters")
  .refine((v) => {
    try {
      const parsed = new URL(v);
      return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch {
      return false;
    }
  }, "Enter a valid http(s) URL");

const optionalHttpUrlSchema = z
  .union([httpUrlSchema, z.literal("")])
  .optional()
  .transform((v) => (v === "" || v === undefined ? null : v));

const technologiesSchema = z
  .array(z.string().trim().max(60, "Each technology must be at most 60 characters"))
  .max(MAX_TECHNOLOGIES, `At most ${MAX_TECHNOLOGIES} technologies`)
  .transform((values) => {
    const seen = new Set<string>();
    return values
      .map((v) => v.trim())
      .filter((v) => {
        if (!v) return false;
        const key = v.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  });

const isoDateSchema = z
  .string()
  .trim()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Use the date picker")
  .refine((v) => !Number.isNaN(Date.parse(v)), "Enter a valid date");

// --- Section 1 ---

export const basicInfoSchema = z.object({
  headline: z.string().trim().min(3, "Write at least a few words").max(200),
  college: z.string().trim().min(2, "Enter your college").max(200),
  degree: z.enum(degreeValues, { required_error: "Select your degree" }),
  branch: z.enum(branchValues, { required_error: "Select your branch" }),
  graduation_year: z.coerce
    .number({ invalid_type_error: "Select your graduation year" })
    .int()
    .min(MIN_GRADUATION_YEAR)
    .max(MAX_GRADUATION_YEAR),
  location: z.string().trim().min(2, "Enter your location").max(120),
  target_role: z.enum(targetRoleValues, { required_error: "Select a target role" }),
});

export type BasicInfoForm = z.infer<typeof basicInfoSchema>;

// --- Section 2 ---

/** Accepts a bare username or a github.com profile URL; the backend
 * normalizes both to a username, so this only has to reject what is
 * obviously neither. */
const githubUsernameSchema = z
  .string()
  .trim()
  .min(1, "Enter your GitHub username")
  .max(200)
  .refine((v) => {
    if (!v.includes("/")) return /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/.test(v);
    try {
      const parsed = new URL(v.startsWith("http") ? v : `https://${v}`);
      if (parsed.hostname.replace(/^www\./, "") !== "github.com") return false;
      return parsed.pathname.split("/").filter(Boolean).length === 1;
    } catch {
      return false;
    }
  }, "Enter a GitHub username or https://github.com/<username>");

export const technicalSchema = z.object({
  github_username: githubUsernameSchema,
  coding_profiles: z
    .array(
      z.object({
        platform: z.enum(platformValues),
        handle: z
          .string()
          .trim()
          .min(1, "Enter your handle")
          .max(100)
          .regex(/^[A-Za-z0-9._-]+$/, "Letters, numbers, dots, hyphens and underscores only"),
      }),
    )
    .min(1, "Add at least one competitive programming profile")
    .superRefine((items, ctx) => {
      const seen = new Set<string>();
      items.forEach((item, index) => {
        if (seen.has(item.platform)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "This platform is already listed",
            path: [index, "platform"],
          });
        }
        seen.add(item.platform);
      });
    }),
});

export type TechnicalForm = z.infer<typeof technicalSchema>;

// --- Section 3 ---

export const projectsSchema = z.object({
  projects: z
    .array(
      z
        .object({
          kind: z.enum(["repository", "described"] as const),
          title: z.string().trim().min(2, "Enter a title").max(200),
          description: z.string().trim().max(4000).optional().or(z.literal("")),
          repo_url: optionalHttpUrlSchema,
          technologies: technologiesSchema,
        })
        .superRefine((project, ctx) => {
          // Mirrors the backend's kind/shape rule so the error lands on the
          // right input instead of arriving as a generic 422.
          if (project.kind === "repository") {
            if (!project.repo_url) {
              ctx.addIssue({
                code: z.ZodIssueCode.custom,
                message: "A repository project needs a repo URL",
                path: ["repo_url"],
              });
            }
          } else {
            if (project.repo_url) {
              ctx.addIssue({
                code: z.ZodIssueCode.custom,
                message: "Remove the URL or switch this to a repository",
                path: ["repo_url"],
              });
            }
            if (!project.description?.trim()) {
              ctx.addIssue({
                code: z.ZodIssueCode.custom,
                message: "Describe the project",
                path: ["description"],
              });
            }
          }
        }),
    )
    .max(MAX_PROJECTS, `At most ${MAX_PROJECTS} projects`)
    .superRefine((projects, ctx) => {
      const seen = new Set<string>();
      projects.forEach((project, index) => {
        if (!project.repo_url) return;
        const key = project.repo_url.toLowerCase();
        if (seen.has(key)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "This repository is already listed",
            path: [index, "repo_url"],
          });
        }
        seen.add(key);
      });
    }),
});

export type ProjectsForm = z.infer<typeof projectsSchema>;

// --- Section 4 ---

export const certificatesSchema = z.object({
  certificates: z
    .array(
      z.object({
        title: z.string().trim().min(2, "Enter a title").max(200),
        issuer: z.string().trim().min(2, "Enter the issuer").max(200),
        issued_at: z
          .union([isoDateSchema, z.literal("")])
          .optional()
          .transform((v) => (v === "" || v === undefined ? null : v)),
        credential_url: optionalHttpUrlSchema,
      }),
    )
    .max(10, "At most 10 certificates"),
});

export type CertificatesForm = z.infer<typeof certificatesSchema>;

// --- Section 5 ---

export const experiencesSchema = z.object({
  experiences: z
    .array(
      z
        .object({
          company_name: z.string().trim().min(2, "Enter the company").max(200),
          title: z.string().trim().min(2, "Enter your role").max(200),
          employment_type: z.enum(employmentTypeValues),
          start_date: isoDateSchema,
          end_date: z
            .union([isoDateSchema, z.literal("")])
            .optional()
            .transform((v) => (v === "" || v === undefined ? null : v)),
          description: z.string().trim().max(4000).optional().or(z.literal("")),
          technologies: technologiesSchema,
        })
        .superRefine((experience, ctx) => {
          if (experience.end_date && experience.end_date < experience.start_date) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              message: "End date cannot be before the start date",
              path: ["end_date"],
            });
          }
        }),
    )
    .max(10, "At most 10 entries"),
});

export type ExperiencesForm = z.infer<typeof experiencesSchema>;
