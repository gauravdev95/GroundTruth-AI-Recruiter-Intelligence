import { z } from "zod";

/**
 * Mirrors `apps/backend/src/domains/student/schemas.py` for UX only — the
 * server revalidates everything and is authoritative. Keep the two in step:
 * a rule relaxed here but not there just moves the error from inline to a
 * toast.
 */

const MAX_PROJECTS = 3;
const MAX_TECHNOLOGIES = 15;
const MAX_TARGET_ROLES = 3;
const MAX_CERTIFICATES = 5;
const MAX_EXPERIENCES = 5;
/** Tags on a single experience entry. Tighter than `MAX_TECHNOLOGIES`, which
 * bounds a project's claimed stack. */
const MAX_EXPERIENCE_TECHNOLOGIES = 8;
/** The contribution note on an onboarding-linked repository. Short on purpose:
 * the field asks what you built, not for a project write-up. The profile
 * editor's `description` on the same column allows more. */
export const MAX_CONTRIBUTION_CHARS = 200;

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

const platformValues = [
  "leetcode",
  "codeforces",
  "hackerrank",
  "codechef",
  "atcoder",
  "geeksforgeeks",
  "other",
] as const;
const employmentTypeValues = [
  "internship",
  "full_time",
  "freelance",
  "part_time",
  "research",
  "open_source",
] as const;

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

/** An experience entry's stack, capped tighter than a project's claimed
 * technologies: this is a tag list on one role, not a repository's manifest. */
const experienceTechnologiesSchema = z
  .array(z.string().trim().max(60, "Each technology must be at most 60 characters"))
  .max(MAX_EXPERIENCE_TECHNOLOGIES, `At most ${MAX_EXPERIENCE_TECHNOLOGIES} technologies`)
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

/**
 * Moved here from `authSchemas.ts` when name and phone came off signup.
 *
 * Optional, unlike `full_name`: a phone number helps a recruiter reach the
 * student but is not needed to build or score a profile, and requiring one
 * at the first section would reintroduce the friction that removing it from
 * signup was meant to remove. An empty string is a valid save and clears it.
 */
const phoneSchema = z
  .string()
  .trim()
  .transform((v) => v.replace(/[\s-]/g, ""))
  .refine((v) => v === "" || /^\+?[1-9]\d{7,14}$/.test(v), "Enter a valid phone number")
  .optional();

export const basicInfoSchema = z.object({
  // Collected here rather than at signup — this is where the student can see
  // what the name is for.
  full_name: z.string().trim().min(2, "Enter your full name").max(200),
  phone_number: phoneSchema,
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
  // One to three. Order is significant — the first is stored as the profile's
  // primary `target_role`, which is the one the matcher indexes — so this
  // rejects duplicates rather than deduplicating: silently dropping a repeat
  // could change which role ends up primary without telling the student.
  target_roles: z
    .array(z.enum(targetRoleValues))
    .min(1, "Pick at least one target role")
    .max(MAX_TARGET_ROLES, `Pick at most ${MAX_TARGET_ROLES} roles`)
    .refine((roles) => new Set(roles).size === roles.length, "Each role may only be picked once"),
  // Optional — see `BasicInfoPayload.about`. No `min`, so an empty textarea is
  // a valid save rather than a validation error on a field nobody has to fill.
  about: z.string().trim().max(2000, "Must be at most 2000 characters").optional(),
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

/** Flags a repeated platform on the offending row rather than on the array, so
 * the error lands next to the select the student has to change. Shared by both
 * schemas below. */
function rejectDuplicatePlatforms(
  items: { platform: string }[],
  ctx: z.RefinementCtx,
): void {
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
}

const codingProfileItemSchema = z
        .object({
          platform: z.enum(platformValues),
          handle: z
            .string()
            .trim()
            .min(1, "Enter your handle")
            .max(100)
            .regex(/^[A-Za-z0-9._-]+$/, "Letters, numbers, dots, hyphens and underscores only"),
          // Both are meaningful only for `other`, which has no URL template on
          // the server — the student supplies the link themselves. Sending
          // either for a named platform is a 422 there, so the form must not
          // let it happen.
          custom_platform_name: z.string().trim().max(60).optional(),
          profile_url: z.union([httpUrlSchema, z.literal("")]).optional(),
        })
        .superRefine((item, ctx) => {
          if (item.platform !== "other") return;
          if (!item.custom_platform_name?.trim()) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              message: "Name the platform",
              path: ["custom_platform_name"],
            });
          }
          if (!item.profile_url?.trim()) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              message: "Paste the full profile URL",
              path: ["profile_url"],
            });
          }
        });

export const technicalSchema = z.object({
  github_username: githubUsernameSchema,
  // No `min` any more. GitHub and coding profiles are separate sections and
  // only GitHub is mandatory, so a profile with no handles is a valid save —
  // requiring one here would reinstate the gate the split removed.
  coding_profiles: z.array(codingProfileItemSchema).superRefine(rejectDuplicatePlatforms),
});

export type TechnicalForm = z.infer<typeof technicalSchema>;

/**
 * Onboarding stage 4, which saves coding profiles alone.
 *
 * An empty array is valid and meaningful: it is what "Skip for now" sends, and
 * what removing every handle sends. A section that could not express "none"
 * would make the first handle a student entered permanent.
 */
export const codingProfilesSchema = z.object({
  coding_profiles: z.array(codingProfileItemSchema).superRefine(rejectDuplicatePlatforms),
});

export type CodingProfilesForm = z.infer<typeof codingProfilesSchema>;

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
          live_demo_url: optionalHttpUrlSchema,
          is_primary: z.boolean().default(false),
          // `claimed_`, not `technologies`: the plain name belongs to the list
          // detected from the repository's dependency manifests during
          // verification, which the candidate cannot write to.
          claimed_technologies: technologiesSchema,
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

      // Mirrors the backend's `reject_multiple_primaries`. The radio group in
      // the form should make this unreachable; it is asserted anyway because a
      // stale field-array index is exactly how two flags survive a delete.
      const primaries = projects.filter((project) => project.is_primary);
      if (primaries.length > 1) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Only one project can be the main project",
          path: [projects.findIndex((p) => p.is_primary), "is_primary"],
        });
      }
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
        // Set by the upload control, not typed. `file_object_key` is present
        // only for a file uploaded during *this* editing session — an already
        // attached one is identified by `existing_file_name` alone, because the
        // server never returns the key.
        file_object_key: z.string().optional(),
        file_name: z.string().optional(),
        file_content_type: z.string().optional(),
        file_size_bytes: z.number().optional(),
        existing_file_name: z.string().optional(),
        remove_file: z.boolean().default(false),
      }),
    )
    .max(MAX_CERTIFICATES, `At most ${MAX_CERTIFICATES} certificates`),
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
          technologies: experienceTechnologiesSchema,
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
    .max(MAX_EXPERIENCES, `At most ${MAX_EXPERIENCES} entries`),
});

export type ExperiencesForm = z.infer<typeof experiencesSchema>;
