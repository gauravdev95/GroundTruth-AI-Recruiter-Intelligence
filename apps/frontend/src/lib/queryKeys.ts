/**
 * Central query-key registry. One namespace per domain, each a factory
 * function (even for a fixed key) so a later parameterized variant
 * (`queryKeys.jobs.detail(id)`) doesn't change the calling convention.
 *
 * Only `auth.me` is wired to a real query today — `AuthContext` currently
 * calls `authApi.me()` directly during its silent-refresh-on-load effect,
 * not through `useQuery`. This entry documents the key a future
 * `useQuery({ queryKey: queryKeys.auth.me() })` migration would use, and
 * is the pattern new domains (`candidate`, `recruiter`, `jobs`, ...) append
 * their own namespace to.
 */
export const queryKeys = {
  auth: {
    me: () => ["auth", "me"] as const,
  },
  studentProfile: {
    all: () => ["student", "profile"] as const,
    completeness: () => ["student", "profile", "completeness"] as const,
    section: (section: string) => ["student", "profile", "section", section] as const,
    // Nested under `all` on purpose: every section save already invalidates
    // that prefix, so the setup stepper and its percentage refresh from the
    // server after a save without any caller having to remember this key.
    setupState: () => ["student", "profile", "setup-state"] as const,
  },
  resume: {
    all: () => ["student", "resume"] as const,
    uploads: () => ["student", "resume", "uploads"] as const,
    draft: (uploadId: string) => ["student", "resume", "draft", uploadId] as const,
    job: (jobId: string) => ["jobs", jobId] as const,
  },
  github: {
    repos: () => ["student", "github", "repos"] as const,
  },
  interview: {
    latestForProject: (projectId: string) => ["student", "interview", "project", projectId] as const,
    state: (interviewId: string) => ["student", "interview", interviewId] as const,
    report: (interviewId: string) => ["student", "interview", interviewId, "report"] as const,
  },
  studentFeed: {
    jobs: () => ["student", "matches"] as const,
  },
  recruiterJobs: {
    all: () => ["recruiter", "jobs"] as const,
    detail: (jobId: string) => ["recruiter", "jobs", jobId] as const,
    matches: (jobId: string) => ["recruiter", "jobs", jobId, "matches"] as const,
    asyncJob: (asyncJobId: string) => ["recruiter", "async-job", asyncJobId] as const,
  },
  notifications: {
    all: () => ["notifications"] as const,
  },
  asyncJobs: {
    all: () => ["jobs", "mine"] as const,
  },
  applications: {
    mine: () => ["student", "applications"] as const,
    detail: (applicationId: string) => ["student", "applications", applicationId] as const,
    messages: (applicationId: string) => ["applications", applicationId, "messages"] as const,
  },
  studentAnalytics: {
    summary: () => ["student", "analytics", "summary"] as const,
  },
  pipeline: {
    board: (jobId: string) => ["recruiter", "jobs", jobId, "pipeline"] as const,
    application: (applicationId: string) => ["recruiter", "applications", applicationId] as const,
    notes: (applicationId: string) => ["recruiter", "applications", applicationId, "notes"] as const,
  },
  evidence: {
    candidate: (candidateProfileId: string) => ["recruiter", "candidates", candidateProfileId, "evidence"] as const,
  },
  recruiterAnalytics: {
    funnel: () => ["recruiter", "analytics", "funnel"] as const,
  },
} as const;
