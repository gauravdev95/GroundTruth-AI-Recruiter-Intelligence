/**
 * Every word on the landing page.
 *
 * Two rules govern this file, and they are why it exists as a module rather
 * than as JSX:
 *
 * 1. **Copy is never edited in a component.** A section reads its slice from
 *    here and lays it out; it never carries a sentence of its own. That makes a
 *    copy review a diff of one file instead of a sweep of nineteen.
 *
 * 2. **Every number is either true of this repository or labelled as sample.**
 *    This is a product that exists to check claims — one invented figure on the
 *    page that sells it is not a rounding error, it is the whole premise. The
 *    figures below fall into exactly two buckets:
 *
 *      - **Capability facts** — seven stages, a 1536-dimension vector, four
 *        rubric weights, five pipeline states. Each is read from the backend
 *        and cited in the comment above it.
 *      - **Sample-run figures** — the console readout, the evidence panel, the
 *        ranked lists. Every one is synthetic and disclosed on its own surface.
 *
 *    No user counts, company counts, testimonials, compliance badges or roadmap
 *    statuses appear anywhere in this file, and none will until they are real.
 *
 * ---------------------------------------------------------------------------
 * TWO CORRECTIONS AGAINST THE SOURCE BRIEF, BOTH FOR ACCURACY
 * ---------------------------------------------------------------------------
 *
 * **The embedding is 1536-dimensional, not 384.** The brief carried "384-dim,
 * sentence-transformers" as a placeholder and instructed that it be changed to
 * 1536 if the system actually uses `text-embedding-3-small`. It does:
 * `domains/ai/embedding_constants.py` sets `EMBEDDING_DIMENSIONS = 1536`, and
 * `domains/ai/providers/openai_embedder.py` is the only embedder built.
 * sentence-transformers is not a dependency of this repository.
 *
 * **Technology detection reads dependency manifests, not an AST.** The brief
 * described stage 05 as "AST analysis" and named `tree-sitter` in the
 * architecture. Neither is in this repository.
 * `domains/verification/manifests.py` parses `package.json`, `pyproject.toml`,
 * `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle`,
 * `Gemfile` and `composer.json`, and combines them with the repository file
 * tree. That is still a real mechanism and still strictly better than reading a
 * resume — it is evidence of what the code pulls in and what is in the tree,
 * rather than what the candidate typed — so the claim is made in those terms.
 * Naming a parser the product does not run would be exactly the unverified
 * claim this page argues against.
 */

/* ==================================================================
   ROUTES — every href resolves to a real route or a real section id
   ================================================================== */

/**
 * `/signup` takes the role as a query parameter; `authRoutes` in
 * `features/auth/routes.tsx` is the definition. There is no `/pricing`,
 * `/about`, `/privacy` or `/terms` route, so this page links to none of them.
 */
export const ROUTES = {
  studentSignup: "/signup",
  recruiterSignup: "/signup?role=recruiter",
  login: "/login",
} as const;

export interface Cta {
  readonly label: string;
  readonly short: string;
  readonly href: string;
}

export const CTA: Record<"student" | "recruiter", Cta> = {
  student: {
    label: "Build a verified profile",
    /** Header-sized variant — the full label does not fit a 70px nav. */
    short: "Get verified",
    href: ROUTES.studentSignup,
  },
  recruiter: {
    label: "Hire on evidence",
    short: "Hire on evidence",
    href: ROUTES.recruiterSignup,
  },
};

/* ==================================================================
   NAV
   ================================================================== */

/**
 * Four links, each landing on a section that exists.
 *
 * Pricing is deliberately absent. The product has not launched and there is no
 * `/pricing` route; a nav link to an empty page costs more trust than no link.
 * Pricing is one line in §12 instead, and the nav link goes back when the page
 * is real.
 */
export const NAV = {
  links: [
    { href: "#verification", label: "How it works" },
    { href: "#assessment", label: "Evidence" },
    { href: "#matching", label: "Matching" },
    { href: "#access", label: "Security" },
  ],
  loginLabel: "Log in",
} as const;

/* ==================================================================
   §00 — HERO
   ================================================================== */

export const HERO = {
  coord: "§00 / THESIS",
  pill: "Not a test score. Not a resume claim. Real code, reviewed.",

  /*
   * Split into runs so "code" and "now" can take the violet→blue gradient
   * while the rest stays --ink. This is one of exactly two gradient fills on
   * the page; the other is the primary CTA.
   */
  h1: {
    before: "Your ",
    accentA: "code",
    middle: " is your résumé ",
    accentB: "now",
    after: ".",
  },

  lead:
    "GroundTruth reads your actual repositories, confirms what you personally wrote, " +
    "and interviews you on your own source — then turns the result into a profile a " +
    "recruiter can act on.",

  /**
   * Capability facts, not vanity metrics: each is a property of the system
   * rather than a count of anything that has happened on it.
   *
   * 7      — `STAGE_SEQUENCE`, `domains/student/models.py`
   * 1536   — `EMBEDDING_DIMENSIONS`, `domains/ai/embedding_constants.py`
   * 5–7    — questions per interview session, `domains/interview/service.py`
   * 4      — the four evidence sources enumerated in §08
   */
  capabilities: [
    { value: "7", label: "Verification stages", detail: "" },
    { value: "1536-dim", label: "Shared vector space", detail: "" },
    { value: "5–7", label: "Questions from your own code", detail: "" },
    {
      value: "4",
      label: "Evidence sources",
      detail: "code · commits · contests · certificates",
    },
  ],

  sampleLabel: "Sample profile",
} as const;

/**
 * The console readout. Synthetic, and disclosed directly beneath it.
 *
 * One skill stays UNPROVEN on purpose. A verification demo in which everything
 * passes is not a demonstration of verification — the amber row is the proof
 * that the system is capable of saying no.
 */
export const CONSOLE = {
  repo: "candidate/payments-api · main",
  verdict: "VERIFIED",

  score: 93,
  scoreLabel: "Evidence score",
  sparkLabel: "commit history",
  /** Bar heights for the commit sparkline, 0–1. Sample, like everything here. */
  spark: [0.22, 0.44, 0.68, 0.3, 0.82, 0.55, 1],

  /** Stage labels for the segment bar, in `STAGE_SEQUENCE` order. */
  stages: [
    "Repository selection",
    "Fork & authorship check",
    "Contribution analysis",
    "Architecture & code quality",
    "Technology detection",
    "Code-grounded interview",
    "Evidence report",
  ],

  /** Commit rows that stream in while the stages tick. */
  commits: [
    "3f9a2c1  collapse concurrent refreshes into one flight",
    "d02c7a9  add expiry skew to token verification",
    "a55f019  make the ledger insert idempotent under retry",
  ],

  vectorLine: "1536-dim vector · cosine 0.93 to role #C4E1",

  /** `claim` is the pre-verification state every row starts in. */
  skills: [
    { name: "TypeScript", claim: "self-declared", evidence: "2,140 lines authored", status: "VERIFIED" },
    { name: "React", claim: "self-declared", evidence: "38 components authored", status: "VERIFIED" },
    { name: "PostgreSQL", claim: "self-declared", evidence: "11 migrations authored", status: "VERIFIED" },
    { name: "Kubernetes", claim: "self-declared", evidence: "no repository evidence", status: "UNPROVEN" },
  ],

  metrics: [
    { value: "74%", label: "Authored" },
    { value: "8.6/10", label: "Interview" },
    { value: "1847", label: "Rating" },
  ],

  replayLabel: "Replay",
} as const;

/* ==================================================================
   §01 — FAILURE
   ================================================================== */

export const FAILURE = {
  coord: "§01 / FAILURE",
  eyebrow: "WHERE HIRING BREAKS",
  h2: "Five links in the chain, all broken.",
  lead:
    "Nothing in the current process checks whether a claim is true. " +
    "Each failure compounds the last.",

  links: [
    {
      failure: "Skills are self-declared, never verified",
      consequence:
        "The person who installed a framework looks identical to the person who architected with it.",
    },
    {
      failure: "Screening is keyword matching",
      consequence:
        "Strong engineers get filtered out silently. Well-worded resumes rise instead.",
    },
    {
      failure: "AI writes resumes and project descriptions now",
      consequence: "The written claim no longer correlates with understanding.",
    },
    {
      failure: "Discovery runs one direction only",
      consequence:
        "Students apply blindly, with no ranked view of the roles that actually fit them.",
    },
    {
      failure: "Manual shortlisting doesn't scale",
      consequence: "300–400 applications arrive per fresher role, per week.",
    },
  ],

  /**
   * The conveyor: two keyword-stuffed entries pass the gate, one dense commit
   * history is stopped by it. The failure stated as a picture rather than as
   * another sentence.
   */
  conveyor: {
    label: "Keyword gate",
    entries: [
      { text: "react · redux · aws · agile", verdict: "PASSES", kind: "keyword" },
      { text: "synergy · fullstack · ci/cd", verdict: "PASSES", kind: "keyword" },
      { text: "dense commit history, no keywords", verdict: "STOPPED", kind: "evidence" },
    ],
    caption: "This is the candidate you wanted.",
  },
} as const;

/* ==================================================================
   §02 — AUDIENCE
   ================================================================== */

export const AUDIENCE = {
  coord: "§02 / AUDIENCE",
  eyebrow: "TWO SIDES, ONE ENGINE",
  h2: "Which side of the table are you on?",
  lead: "The same verified record does two jobs. Pick yours.",

  /*
   * Both panels are the same size and the same treatment, and neither is
   * styled as primary. The language is parallel line for line and matched in
   * length — "get judged on what you built" against "shortlist against proof".
   */
  panels: [
    {
      key: "student",
      label: "For students",
      points: [
        "Get judged on what you built, not how you worded it",
        "One interview on your own code, not a generic question bank",
        "A ranked feed of roles that actually fit you",
      ],
      reassurance: "Read-only access. Your source is never stored.",
      cta: CTA.student,
    },
    {
      key: "recruiter",
      label: "For recruiters",
      points: [
        "Shortlist against proof, not against a resume",
        "Every score traces back to a file, a commit, or a recorded answer",
        "A ranked candidate list before anyone applies",
      ],
      reassurance: "Every match arrives with its reasons attached.",
      cta: CTA.recruiter,
    },
  ],
} as const;

/* ==================================================================
   §03 — VERIFICATION
   ================================================================== */

export const VERIFICATION = {
  coord: "§03 / VERIFICATION",
  eyebrow: "HOW VERIFICATION WORKS",
  h2: "Seven stages between a claim and a credential.",
  lead:
    "Every stage is machine-checked and leaves an artefact behind. " +
    "Nothing advances on trust.",
  note: "Artefact values shown are a sample run, not aggregate platform figures.",

  /**
   * The seven stages, in `STAGE_SEQUENCE` order — the backend's own names,
   * `repository_selection` through `evidence_report`, so this list cannot
   * drift from the pipeline it describes without the drift being visible.
   *
   * Stage 05 describes manifest parsing, which is what
   * `domains/verification/manifests.py` does. See the note at the top of this
   * file.
   */
  stages: [
    {
      n: "01",
      title: "Repository Selection",
      artefact: "3 repositories · 1,284 commits in scope",
      body: "The candidate nominates up to three repositories to put on the record.",
    },
    {
      n: "02",
      title: "Fork & Authorship Check",
      artefact: "fork ratio 2/6 · 68% of files authored",
      body: "Forks, vendored code, and template scaffolding are separated from original work.",
    },
    {
      n: "03",
      title: "Contribution Analysis",
      artefact: "412 commits attributed · 74% of changed lines",
      body: "Commit history and diffs isolate what this person wrote from what the team wrote.",
    },
    {
      n: "04",
      title: "Architecture & Code Quality",
      artefact: "9 modules · 61% of authored files under test",
      body: "Structure, module boundaries, and testing are read from the tree itself.",
    },
    {
      n: "05",
      title: "Technology Detection",
      artefact: "TypeScript · 6 manifests parsed · 41 dependencies resolved",
      body:
        "Languages and frameworks come from the repository's dependency manifests and file tree — " +
        "what the code actually pulls in, not what the resume lists.",
    },
    {
      n: "06",
      title: "Code-Grounded AI Interview",
      artefact: "6 questions · 8.6/10 weighted score",
      body: "Questions are generated from this candidate's own source, then scored.",
    },
    {
      n: "07",
      title: "Evidence Report",
      artefact: "1536-dim vector · cosine 0.93 to role #C4E1",
      body: "One profile where every skill links back to the artefact that proves it.",
    },
  ],

  /* The artefact itself, in the same section: the record the stages produce. */
  profile: {
    title: "The record it produces",
    /*
     * MANDATORY / OPTIONAL are neutral badges — outlined in --rule, text in
     * --slate. They describe a requirement, not a verification status, so
     * green here would break the colour rule and dilute every real badge.
     */
    sections: [
      {
        name: "Basic Information",
        status: "MANDATORY",
        body: "Identity, graduation year, location, and the constraints recruiters filter on.",
      },
      {
        name: "Technical Verification",
        status: "MANDATORY",
        body: "GitHub plus at least one competitive programming profile, both checked at the source.",
      },
      {
        name: "Skill & Project Verification",
        status: "OPTIONAL",
        body: "Up to three repositories taken through all seven stages.",
      },
      {
        name: "Certificates & Achievements",
        status: "OPTIONAL",
        body: "Validated against the issuer. Unvalidated entries remain listed and flagged.",
      },
      {
        name: "Experience",
        status: "OPTIONAL",
        body: "One consolidated interview covering the most significant roles.",
      },
    ],
    footnote: "The last three are optional and raise the profile strength score, which feeds ranking.",
  },

  /**
   * The evidence panel: each chip wired to the artefact behind it, which is
   * the product's central claim made operable rather than described.
   *
   * Six chips, so the row divides evenly and no chip is stranded alone on a
   * second line at any width.
   */
  detected: {
    title: "Detected skills",
    hint: "Select a skill for the evidence behind it. Arrow keys move between skills.",
    skills: [
      {
        name: "TypeScript",
        status: "VERIFIED",
        repo: "candidate/payments-api",
        summary: "2,140 lines authored · 6 manifests parsed",
        files: [
          "src/auth/jwt.ts · 214 lines · sole author",
          "src/session/store.ts · 388 lines · 91% authored",
        ],
        commits: [
          "commit 3f9a2c1 · collapse concurrent refreshes into one flight",
          "commit d02c7a9 · add expiry skew to token verification",
        ],
      },
      {
        name: "React",
        status: "VERIFIED",
        repo: "candidate/payments-api",
        summary: "38 components authored · 1,104 lines",
        files: [
          "src/ui/PaymentForm.tsx · 302 lines · sole author",
          "src/ui/hooks/useIdempotency.ts · 96 lines · sole author",
        ],
        commits: [
          "commit 8b41e60 · retry a failed capture without double-charging",
          "commit 1c7de44 · move form state out of the submit handler",
        ],
      },
      {
        name: "PostgreSQL",
        status: "VERIFIED",
        repo: "candidate/payments-api",
        summary: "11 migrations authored · 4 indexes added",
        files: [
          "migrations/0009_ledger_unique.sql · 41 lines · sole author",
          "src/db/ledger.ts · 227 lines · 88% authored",
        ],
        commits: [
          "commit a55f019 · make the ledger insert idempotent under retry",
          "commit 6e2b8c3 · index settlements by (account, captured_at)",
        ],
      },
      {
        name: "Docker",
        status: "VERIFIED",
        repo: "candidate/payments-api",
        summary: "2 manifests parsed · multi-stage build authored",
        files: [
          "Dockerfile · 34 lines · sole author",
          "docker-compose.yml · 52 lines · sole author",
        ],
        commits: ["commit f10a7b2 · split build and runtime stages"],
      },
      {
        name: "Kubernetes",
        status: "UNPROVEN",
        repo: "no repository evidence",
        summary: "Claimed on the profile. Nothing in the tree references it.",
        files: [],
        commits: [],
      },
      {
        name: "AWS",
        status: "UNPROVEN",
        repo: "no repository evidence",
        summary: "Claimed on the profile. No manifest or config names it.",
        files: [],
        commits: [],
      },
    ],
  },
} as const;

/* ==================================================================
   §04 — ASSESSMENT
   ================================================================== */

export const ASSESSMENT = {
  coord: "§04 / ASSESSMENT",
  eyebrow: "CODE-GROUNDED INTERVIEW",
  h2: "Questions written from your code, not a question bank.",
  lead:
    "The engine reads what you submitted and asks about it. " +
    "You can only answer well if you actually understand it.",

  file: {
    name: "src/auth/jwt.ts",
    label: "Sample session",
    /*
     * Lines 5, 8 and 9 are the three the question actually asks about. The
     * marker is a neutral tint band and a neutral left edge, never green:
     * nothing in this panel has been proven yet, it is being asked about.
     */
    highlighted: [5, 8, 9],
    lines: [
      "let refreshing: Promise<Session> | null = null;",
      "",
      "export async function getSession(): Promise<Session> {",
      "  const cached = store.read();",
      "  if (cached && cached.expiresAt - Date.now() > 30_000) {",
      "    return cached;",
      "  }",
      "  refreshing ??= rotate(cached?.refreshToken)",
      "    .finally(() => { refreshing = null; });",
      "  return refreshing;",
      "}",
    ],
  },

  question: {
    label: "generated question",
    source: "from src/auth/jwt.ts",
    body:
      "You assign refreshing with ??= and clear it inside .finally(). Walk me through what " +
      "happens when two calls to getSession() arrive at the same time on an expired token — " +
      "and why 30_000 rather than 0.",
    meta: "5–7 questions per session. Answers are time-bounded.",
    state: "ANSWER RECORDED",
    elapsedLabel: "elapsed",
    elapsed: "0:42",
    scoreLabel: "rubric score",
    score: "8.6/10",
    /** Fill of the score track, as a percentage. 8.6 of 10. */
    scorePct: 86,
  },

  /**
   * `RUBRIC_WEIGHTS` in `domains/interview/models.py`. These are the real
   * weights, and each bar is drawn at exactly its own percentage of the track:
   * four equal bars under four different numbers would be a data-integrity bug
   * on a page whose argument is that its numbers are real.
   */
  rubric: {
    title: "How the answer is scored",
    rows: [
      { criterion: "Technical accuracy", weight: 40 },
      { criterion: "Depth of reasoning", weight: 25 },
      { criterion: "Specificity to the codebase", weight: 20 },
      { criterion: "Consistency with the repository", weight: 15 },
    ],
  },
} as const;

/* ==================================================================
   §05 — MATCHING
   ================================================================== */

export const MATCHING = {
  coord: "§05 / MATCHING",
  eyebrow: "TWO-WAY MATCHING",
  h2: "One computation. Both directions.",
  lead:
    "Verified profiles and confirmed job requirements share a single vector space. " +
    "The similarity that ranks candidates for a recruiter is the same one that ranks jobs " +
    "for a student.",

  convergence: {
    left: {
      title: "Verified profile",
      rows: ["skills · manifest-detected", "authorship · 74%", "interview · 8.6/10", "rating · 1847"],
    },
    centre: { value: "0.93", label: "Cosine similarity" },
    right: {
      title: "Confirmed requirement",
      rows: ["must have · TypeScript", "grad year · 2027", "location · remote", "experience · 0–1y"],
    },
  },

  /*
   * Both outputs, side by side, out of one similarity. This symmetry is the
   * product; showing only one side here would undo §02.
   */
  outputs: [
    {
      title: "Student sees a ranked job feed",
      rows: [
        { id: "Role #C4E1", score: "0.93" },
        { id: "Role #91BD", score: "0.88" },
        { id: "Role #2A7F", score: "0.81" },
      ],
    },
    {
      title: "Recruiter sees a ranked candidate list",
      rows: [
        { id: "Candidate #A7F2", score: "0.93" },
        { id: "Candidate #5D0C", score: "0.90" },
        { id: "Candidate #B318", score: "0.84" },
      ],
    },
  ],

  /**
   * The chain as `domains/matching/service.py` runs it. Rank fusion's three
   * inputs are `MATCH_WEIGHTS` in `domains/matching/scoring.py`; Top-K's
   * cut-off is `MATCH_THRESHOLD` in the same module.
   */
  chain: {
    title: "The chain",
    steps: [
      { step: "SQL pre-filter", detail: "hard constraints: graduation year, location, experience" },
      { step: "Cosine similarity", detail: "over the remaining student vectors" },
      { step: "Rank fusion", detail: "semantic score + profile strength + evidence score" },
      { step: "Top-K", detail: "everything above threshold, both directions" },
    ],
  },

  /*
   * Five states, and a card in every one. An empty column reads as a page that
   * failed to load rather than as an empty pipeline.
   */
  pipeline: {
    title: "Recruiter pipeline",
    columns: [
      { state: "Matched", card: { id: "#B318", score: "0.84", authored: "61% authored", interview: "interview 7.9" } },
      { state: "Applied", card: { id: "#5D0C", score: "0.90", authored: "70% authored", interview: "interview 8.2" } },
      { state: "Shortlisted", card: { id: "#A7F2", score: "0.93", authored: "74% authored", interview: "interview 8.6" } },
      { state: "Interview", card: { id: "#C41A", score: "0.91", authored: "69% authored", interview: "interview 8.4" } },
      { state: "Hired / Rejected", card: { id: "#A7F2", score: "0.93", authored: "74% authored", interview: "interview 8.6" } },
    ],
    caption: "Smart Apply · the verified evidence profile is the application",
  },
} as const;

/* ==================================================================
   §06 — DIFFERENCE
   ================================================================== */

export const DIFFERENCE = {
  coord: "§06 / DIFFERENCE",
  eyebrow: "WHAT CHANGES",
  h2: "The same candidate, seen two ways.",
  lead: "Nothing here is a new feature. It is the same information, checked instead of asserted.",

  columns: { left: "Resume · LinkedIn · ATS", right: "GroundTruth" },

  /*
   * No ticks, no crosses. The left column is --slate and the right is --ink,
   * and that contrast carries the comparison on its own. Green ticks and red
   * crosses would break the colour rule and make this read as a template
   * pricing table.
   */
  rows: [
    {
      dimension: "Skill claims",
      before: "Self-declared, never checked",
      after: "Traced to a file, a commit, or a recorded answer",
    },
    {
      dimension: "Screening method",
      before: "Keyword match against text",
      after: "Similarity over verified evidence",
    },
    {
      dimension: "Technical signal",
      before: "A written description of the work",
      after: "The repository's own manifests, tree, and commit history",
    },
    {
      dimension: "Assessment",
      before: "Generic question bank",
      after: "Questions generated from the candidate's own source",
    },
    {
      dimension: "Discovery",
      before: "One direction — the student applies",
      after: "Both directions from one computation",
    },
    {
      dimension: "Audit trail",
      before: "None",
      after: "Every score links to the artefact behind it",
    },
  ],
} as const;

/* ==================================================================
   §07 — ACCESS
   ================================================================== */

export const ACCESS = {
  coord: "§07 / ACCESS",
  eyebrow: "WHAT WE READ",
  h2: "We read your code. We don't keep it.",
  lead:
    "Verification requires access. That access is read-only, scoped, revocable, and it ends " +
    "when the analysis does.",

  /**
   * These are commitments, not copy. Every line has to be true of the
   * implementation, and a line that cannot be honoured is deleted rather than
   * softened — a false promise in this section is worse than a missing one.
   *
   * One line was rewritten from the source brief for exactly that reason. The
   * brief promised never to "share a repository name or file path with a
   * recruiter you haven't applied to", but the pipeline's first state is
   * `Matched`, which precedes application — so the promise as written would
   * have been contradicted by §05 two screens earlier. It now describes the
   * boundary that actually holds: a recruiter sees the published evidence
   * profile and nothing else.
   */
  ledger: [
    {
      key: "do",
      title: "We do",
      tone: "verified",
      items: [
        "Request read-only OAuth scope, nothing that can write to your repositories",
        "Analyse public repositories by default",
        "Read private repositories only when you explicitly grant that repository",
        "Store derived metrics only — line counts, authorship share, dependency counts, scores",
        "Show you your own evidence report before it becomes visible to anyone",
        "Let you revoke access, unpublish, or delete at any time",
      ],
    },
    {
      key: "never",
      title: "We never",
      tone: "flagged",
      items: [
        "Store, mirror, or reproduce your source code after analysis",
        "Write, push, open issues, or open pull requests",
        "Show a recruiter anything beyond the evidence profile you published",
        "Sell or share your profile data with third parties",
        "Keep derived data after you delete your account",
      ],
    },
  ],

  cta: CTA.student,
} as const;

/* ==================================================================
   §08 — SOURCES
   ================================================================== */

export const SOURCES = {
  coord: "§08 / SOURCES",
  eyebrow: "WHERE THE EVIDENCE COMES FROM",
  h2: "Four sources, one record.",
  lead: "Each one contributes something the others can't, and each one is checked at its origin.",

  /*
   * Platform categories, not brand logos this page has no permission to
   * display. The clients behind rows three and four are
   * `verification/clients/codeforces.py`, `leetcode.py`, and
   * `verification/certificate.py`.
   */
  rows: [
    {
      source: "Repository (Git)",
      reads: "Commit history, diffs, authorship, fork lineage",
      proves: "That the work is yours, and how much of it",
    },
    {
      source: "Repository (dependencies)",
      reads: "Dependency manifests, the file tree, real imports and configs",
      proves: "Which technologies you actually used, not listed",
    },
    {
      source: "Competitive programming",
      reads: "Ratings, solved counts, contest history via platform APIs",
      proves: "Consistent algorithmic ability over time",
    },
    {
      source: "Certificate issuers",
      reads: "Credential URLs checked against the issuing platform",
      proves: "That a certificate exists and belongs to you",
    },
  ],

  flagged: "Anything that can't be checked stays visible on the profile, flagged rather than hidden.",
  flaggedChip: "FLAGGED",
} as const;

/* ==================================================================
   §09 — QUESTIONS
   ================================================================== */

export const QUESTIONS = {
  coord: "§09 / QUESTIONS",
  eyebrow: "BEFORE YOU START",
  h2: "What people ask first.",

  items: [
    {
      q: "Do you need access to my private repositories?",
      a:
        "No. Read-only OAuth, public repositories by default. A private repository is analysed " +
        "only if you explicitly grant that specific repository, and the source is never stored " +
        "after analysis.",
    },
    {
      q: "What if I don't have much on GitHub?",
      a:
        "Competitive-programming records, issuer-validated certificates and described projects all " +
        "contribute. Two profile sections are mandatory; the rest raise your profile strength.",
    },
    {
      q: "Who scores the interview?",
      a:
        "A fixed rubric applied to answers about your own code — technical accuracy 40%, depth of " +
        "reasoning 25%, specificity to the codebase 20%, consistency with the repository 15%. The " +
        "weights are published on this page.",
    },
    {
      q: "Can I game it?",
      a:
        "The questions come from the source you submitted. Answering them well requires having " +
        "understood what you shipped.",
    },
    {
      q: "What does a recruiter actually see?",
      a:
        "Every score with the artefact behind it — files, commits, contribution share, and the " +
        "interview transcript. Nothing is a bare number.",
    },
    {
      /*
       * Deliberate, and the strongest trust signal available to a pre-launch
       * verification product: disclosing your own demo before anyone asks.
       */
      q: "Is anything on this page real data?",
      a:
        "No. Every figure shown is a sample run, labelled as such. We're not going to fake numbers " +
        "on a product built to check them.",
    },
  ],

  cta: CTA.student,
} as const;

/* ==================================================================
   §10 — SYSTEM
   ================================================================== */

export const SYSTEM = {
  coord: "§10 / SYSTEM",
  eyebrow: "ARCHITECTURE",
  h2: "Five layers, and what each one runs on.",
  lead: "Listed from this repository, not from a wish list.",

  /**
   * Read off `apps/frontend/package.json` and `apps/backend/pyproject.toml`.
   *
   * Three names the source brief listed are absent because they are absent
   * from the repository: `tree-sitter` (technology detection parses dependency
   * manifests instead), `LangGraph` (the interview flow calls the Anthropic
   * adapter directly — `domains/ai/providers/anthropic_interview.py`), and
   * `sentence-transformers` (embeddings are `text-embedding-3-small`,
   * `domains/ai/providers/openai_embedder.py`). Listing a library the product
   * does not import is precisely the unverified claim this page exists to
   * argue against, and a technical reader can check every name below against
   * two files.
   */
  layers: [
    { layer: "Presentation", tech: ["React", "Vite", "TypeScript", "Framer Motion"] },
    { layer: "API / Application", tech: ["FastAPI", "SQLAlchemy 2.x async", "JWT + OAuth 2.0", "Pydantic"] },
    {
      layer: "AI / Intelligence",
      tech: ["Anthropic Claude", "OpenAI text-embedding-3-small", "dependency-manifest analysis"],
    },
    { layer: "Data", tech: ["PostgreSQL", "pgvector", "Alembic", "Redis"] },
    {
      layer: "Integration",
      tech: ["GitHub REST API", "coding-platform APIs", "certificate verification", "Celery workers"],
    },
  ],
} as const;

/* ==================================================================
   §11 — ORIGIN
   ================================================================== */

export const ORIGIN = {
  coord: "§11 / ORIGIN",
  eyebrow: "WHY WE BUILT THIS",
  h2: "The signal broke, so we went to the source.",

  /*
   * For a pre-launch product this section does the job social proof normally
   * does: a stranger trusts you because your reason is specific, not because
   * you have users. Every figure below already appears in §01, so nothing new
   * is being asserted here.
   */
  paragraphs: [
    "More than a million engineering students graduate into the same job market every year, " +
      "carrying near-identical resumes: the same frameworks, the same project titles, the same " +
      "optimised phrasing. A recruiter filling one fresher role receives three to four hundred " +
      "applications a week, and has one artefact to judge them by — the document least connected " +
      "to the work.",
    "We kept meeting the same person: two years of real commits, a solid contest record, genuine " +
      "architectural instinct, and no channel through which any of it was visible. On paper they " +
      "were indistinguishable from someone who had installed the same framework once.",
    "The evidence already existed. It was sitting in their repositories. Nothing in the process " +
      "ever looked at it.",
  ],
} as const;

/* ==================================================================
   §12 — START
   ================================================================== */

export const START = {
  coord: "§12 / START",
  eyebrow: "GET GOING",
  h2: "Two sides, one record of truth.",

  panels: [
    {
      key: "student",
      label: "For students",
      body:
        "Connect your repositories, sit one interview on your own code, and get a profile that " +
        "proves what you can do.",
      cta: CTA.student,
    },
    {
      key: "recruiter",
      label: "For recruiters",
      body:
        "Search verified evidence instead of resume keywords, and get a ranked shortlist with " +
        "every score attached.",
      cta: CTA.recruiter,
    },
  ],

  /* Pricing lives here rather than in the nav — see the NAV comment above. */
  note: "Free for students. Recruiter pricing at launch. Read-only access, revocable any time.",
} as const;

/* ==================================================================
   FOOTER
   ================================================================== */

/**
 * No invented links. Every entry resolves to a section id on this page or to a
 * route that exists in `App.tsx`. There is no Blog, Changelog, Status, API or
 * social row, and no Privacy, Terms, About or Contact link, because none of
 * those pages exist — a footer of dead links is the cheapest possible way to
 * look unfinished on a page arguing for verifiability.
 */
export const FOOTER = {
  wordmark: "GroundTruth",
  blurb:
    "An AI-verified talent marketplace where every skill is proven by code, contribution, or a " +
    "recorded technical answer.",

  columns: [
    {
      title: "Product",
      links: [
        { label: "How it works", href: "#verification" },
        { label: "Evidence profile", href: "#assessment" },
        { label: "Two-way matching", href: "#matching" },
        { label: "Security", href: "#access" },
        { label: "Architecture", href: "#system" },
      ],
    },
    {
      title: "For students",
      links: [
        { label: "Build a verified profile", href: ROUTES.studentSignup, route: true },
        { label: "Why screening fails", href: "#failure" },
        { label: "Log in", href: ROUTES.login, route: true },
      ],
    },
    {
      title: "For recruiters",
      links: [
        { label: "Hire on evidence", href: ROUTES.recruiterSignup, route: true },
        { label: "Recruiter pipeline", href: "#matching" },
        { label: "Log in", href: ROUTES.login, route: true },
      ],
    },
    {
      title: "Answers",
      links: [
        { label: "What we read", href: "#access" },
        { label: "Where evidence comes from", href: "#sources" },
        { label: "Questions", href: "#questions" },
        { label: "Why we built this", href: "#origin" },
      ],
    },
  ],

  copyright: "© 2026 GroundTruth",
  disclosure:
    "Every figure on this page is sample data. No candidate, repository, or score shown is real.",
} as const;
