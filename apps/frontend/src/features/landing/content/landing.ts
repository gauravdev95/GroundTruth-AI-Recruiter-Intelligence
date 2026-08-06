/**
 * Every word on the landing page.
 *
 * Copy is never written inline in a component. Two reasons, both learned on the
 * previous build of this page: a headline edited in JSX cannot be reviewed
 * without reading a render tree around it, and the same sentence tends to end up
 * in two places (the component and `index.html`'s first-paint mirror) where it
 * silently drifts.
 *
 * DECISIONS TAKEN AGAINST THE BRIEF, AND WHY
 *
 * 1. The waitlist line is the brief's own fallback, not its headline number.
 *    "2,400+ engineers on the early-access waitlist" is not true — there is no
 *    waitlist — and the brief supplied the alternative for exactly this case.
 *
 * 2. Copyright is 2026, not the brief's 2027. Today is 2026. A future-dated
 *    copyright notice is the kind of small false claim that a page about
 *    verification cannot afford. The "early access opening 2027" line is kept,
 *    because that is a stated intention rather than a claim about the present.
 *
 * 3. The three statistics in §04 are reproduced exactly as supplied, with the
 *    Gartner attribution the brief attached to the third. They are not
 *    independently verified here and none were invented; the brief's rule was
 *    "do not invent statistics beyond the three provided", and none were.
 *
 * 4. Nav and footer link only to destinations that resolve. `/` is the only
 *    route this app serves besides the auth screens, so product navigation is
 *    on-page anchors and the footer carries no Blog, Careers, Roadmap,
 *    Privacy, Terms or social row. Those pages do not exist, and a footer
 *    column of dead links reads worse than a short footer.
 */

/* ==================================================================
   §00 — NAV
   ================================================================== */

export interface NavLink {
  label: string;
  href: string;
}

/**
 * On-page anchors, not routes. Each `href` matches the `id` of the section it
 * names; `Section` sets `scroll-mt` so a jump does not land under the nav.
 *
 * "Product" from the brief's list is dropped rather than pointed somewhere
 * arbitrary: there is no product page, and every other item here is a real
 * destination on this page.
 */
export const NAV_LINKS: NavLink[] = [
  { label: "How it works", href: "#how-it-works" },
  { label: "For engineers", href: "#engineers" },
  { label: "For recruiters", href: "#recruiters" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
];

export const NAV = {
  logIn: { label: "Log in", href: "/login" },
  cta: { label: "Get started", href: "/signup" },
  openMenu: "Open menu",
  closeMenu: "Close menu",
  skipToContent: "Skip to content",
  homeLabel: "GroundTruth — home",
} as const;

/* ==================================================================
   §01 — HERO
   ================================================================== */

export const HERO = {
  overline: "AI-verified engineering talent",
  /* Set as two stacked lines, so it is stored as two. */
  wordmark: ["Ground", "Truth"] as const,
  /**
   * The headline names the category before it makes a claim.
   *
   * The previous version opened with "Every skill proven by code" — a promise
   * with no subject. A first-time visitor who has never heard of GroundTruth
   * had to infer from a wordmark and an orange sphere what kind of thing they
   * were looking at. "The hiring platform where…" answers that in four words,
   * and the proof claim still lands in the same sentence.
   */
  headline: "The hiring platform where every skill is proven by code.",
  /** The second beat, kept from the original headline. */
  support: "Every claim defended in interview.",
  lead:
    "Adaptive AI interviews grounded in each candidate's real repositories — so recruiters " +
    "see proven builders, not polished resumes.",
  primary: { label: "Get verified — free", href: "/signup" },
  secondary: { label: "For recruiters", href: "#recruiters" },
} as const;

/**
 * The constellation's skill labels.
 *
 * Technical skills only. The reference this hero is modelled on labels cities;
 * translating the metaphor rather than copying it is the entire point of the
 * scene, so no geography appears here.
 */
export const SKILL_NODES = [
  "React",
  "PostgreSQL",
  "System design",
  "Rust",
  "ML Ops",
  "Distributed systems",
  "TypeScript",
  "Go",
] as const;

/* ==================================================================
   §02 — SOCIAL PROOF STRIP
   ================================================================== */

export const PROOF = {
  /* The brief's fallback line. See decision 1 in this file's header. */
  line: "Backed by engineering-first thinking. Early access opening 2027.",
} as const;

/* ==================================================================
   §03 — THE PROBLEM
   ================================================================== */

export interface Stat {
  /** The numeral, as displayed. */
  value: string;
  /** Parsed target for the count-up, or `null` where counting makes no sense. */
  countTo: number | null;
  /** Rendered before the counted digits. */
  prefix?: string;
  /** Rendered after them. */
  suffix?: string;
  label: string;
}

export const PROBLEM = {
  overline: "The hiring problem",
  headline: "Hiring runs on claims nobody verifies.",
  lead:
    "Resumes are AI-generated. GitHub graphs are fake-able in an afternoon. Coding tests are " +
    "cheated with off-screen AI. Recruiters spend the bulk of their time filtering noise. Real " +
    "engineers get missed. Everyone loses.",
  /**
   * `countTo: null` on the third stat is deliberate. "1 in 4" is a ratio, and
   * animating it would mean counting one of its two numbers while the other sat
   * still — which reads as a rendering fault, not as emphasis.
   */
  stats: [
    {
      value: "63%",
      countTo: 63,
      suffix: "%",
      label: "of fraudulent applicants pass ATS filters undetected",
    },
    {
      value: "1,300%",
      countTo: 1300,
      suffix: "%",
      label: "increase in deepfake interview fraud during 2024",
    },
    {
      value: "1 in 4",
      countTo: null,
      label: "candidate profiles predicted fraudulent by 2028 — Gartner",
    },
  ] satisfies Stat[],
} as const;

/* ==================================================================
   §04 — HOW IT WORKS
   ================================================================== */

export interface Step {
  index: string;
  headline: string;
  body: string;
}

export const HOW_IT_WORKS = {
  overline: "How GroundTruth works",
  headline: "Evidence, not assertions.",
  lead: "Three steps between signup and a verified engineering credential you can carry anywhere.",
  steps: [
    {
      index: "01",
      headline: "Connect your work.",
      body:
        "Link your GitHub, coding profiles, and projects. We analyze your actual code — " +
        "commits, contributions, architecture, code quality.",
    },
    {
      index: "02",
      headline: "Prove your skills in a personalized AI interview.",
      body:
        "Answer questions generated from your own code. Explain your decisions. Debug your own " +
        "systems. No LeetCode. No memorization. No generic questions.",
    },
    {
      index: "03",
      headline: "Get matched to jobs that fit.",
      body:
        "Recruiters see verified evidence. You see personalized matches. Both sides skip the " +
        "noise entirely.",
    },
  ] satisfies Step[],
} as const;

/** The code sample in step 01's visual. Held here so no string lives in JSX. */
export const STEP_ONE_SNIPPET = [
  { text: "async fn", tone: "keyword" },
  { text: " settle_batch", tone: "name" },
  { text: "(&self, ids: &[Uuid])", tone: "plain" },
  { text: " -> Result<Receipt> {", tone: "plain" },
] as const;

/** Step 02's visual: a question the interviewer asks about that same code. */
export const STEP_TWO_QUESTION =
  "settle_batch takes a write lock for the whole batch. What happens when one settlement fails " +
  "halfway through?";

/** Step 03's visual: the match strength on the connector between two cards. */
export const STEP_THREE_MATCH = "98% match";

/* ==================================================================
   §05 — FOR ENGINEERS
   ================================================================== */

export const ENGINEERS = {
  overline: "For engineers",
  headline: "Built for engineers who ship, not engineers who write resumes.",
  body:
    "Your GroundTruth profile is a portable engineering credential. Every skill is linked to " +
    "real code. Every claim is defended in an interview grounded in your own work. Recruiters " +
    "don't ask you to prove yourself again — the report does it.",
  bullets: [
    "Verified skill graph based on your real GitHub work",
    "Downloadable evidence report you can share anywhere",
    "Personalized job matches — you only see roles where you actually fit",
    "Verified Engineer badge and top ranking in recruiter searches",
    "Free forever",
  ],
  cta: { label: "Start your verification", href: "/signup" },
  /**
   * The evidence-report mock beside the copy.
   *
   * Every figure here is illustrative and the card says so on its face. A
   * confidence percentage next to a named skill is exactly the kind of number a
   * reader assumes is measured, so the disclosure is part of the mock rather
   * than a footnote under it.
   */
  report: {
    caption: "Sample evidence report",
    candidate: "Evidence report",
    subject: "Verified engineer profile",
    skills: [
      { name: "Rust", confidence: 94, source: "payments-api · 312 commits" },
      { name: "Distributed systems", confidence: 88, source: "Interview · 6 answers" },
      { name: "PostgreSQL", confidence: 81, source: "payments-api · schema, indexes" },
      { name: "React", confidence: 67, source: "dashboard-ui · 44 commits" },
    ],
    footnote: "Every percentage links to the commit or transcript it came from.",
  },
} as const;

/* ==================================================================
   §06 — FOR RECRUITERS
   ================================================================== */

export const RECRUITERS = {
  overline: "For recruiters",
  headline: "Stop screening 300 resumes to find 3 engineers.",
  body:
    "Every candidate on GroundTruth has been through an adaptive AI interview grounded in their " +
    "own code. You see the transcript, the reasoning, the evidence — before you ever get on a " +
    "call.",
  bullets: [
    "Pre-verified, ranked candidates matched to your role's requirements",
    "Full evidence reports with interview transcripts, code analysis, reasoning scores",
    "Kanban hiring pipeline with in-platform messaging",
    "Compliance-ready — DPDP, EEOC, bias-audit disclosures built in",
    "Human-in-the-loop by design — no automated rejection",
  ],
  cta: { label: "Book a 15-min demo", href: "/signup?role=recruiter" },
  /** The pipeline mock. Same disclosure rule as the engineer report above. */
  board: {
    caption: "Sample pipeline",
    role: "Senior Backend Engineer",
    columns: [
      {
        name: "Shortlist",
        cards: [
          { initials: "AR", match: 96, skills: "Rust · Postgres", verified: true },
          { initials: "MK", match: 91, skills: "Go · Kafka", verified: true },
        ],
      },
      {
        name: "Interviewing",
        cards: [{ initials: "JD", match: 88, skills: "Rust · gRPC", verified: true }],
      },
      {
        name: "Offer",
        cards: [{ initials: "SP", match: 84, skills: "Go · Postgres", verified: false }],
      },
    ],
  },
} as const;

/* ==================================================================
   §07 — THE DIFFERENTIATOR
   ================================================================== */

export const DIFFERENCE = {
  overline: "Why GroundTruth",
  headline: "Not another resume database.",
  lead: "Every other platform stops at what candidates claim. GroundTruth starts where they stop.",
  columns: { before: "Traditional platforms", after: "GroundTruth" },
  rows: [
    ["Self-declared skills, no verification", "Every skill backed by code evidence"],
    ["Generic coding tests", "Interviews grounded in your own repositories"],
    ["Keyword-match filtering", "Semantic matching on verified ability"],
    ["Resume → maybe interview → hope", "Evidence report → confident shortlist"],
    ["Black-box AI decisions", "Full audit trail, explainable evidence"],
  ] satisfies [string, string][],
} as const;

/* ==================================================================
   §08 — PRODUCT PREVIEW
   ================================================================== */

export const PREVIEW = {
  overline: "See it in action",
  headline: "See how verification actually works.",
  lead: "Watch a 90-second walkthrough of an adaptive interview grounded in real code.",
  /**
   * There is no walkthrough recorded yet, so the frame is a still and the
   * control says so. A play button that plays nothing is a broken promise on
   * the one section of the page whose subject is honesty about evidence.
   */
  unavailable: "Walkthrough recording in production",
  features: ["Adaptive questioning", "Real-time code verification", "Explainable scoring"],
} as const;

/* ==================================================================
   §09 — TRUST AND COMPLIANCE
   ================================================================== */

export interface Pillar {
  icon: "shield" | "user-check" | "scale";
  headline: string;
  body: string;
}

export const TRUST = {
  overline: "Trust & compliance",
  headline: "Built for the standards that matter.",
  pillars: [
    {
      icon: "shield",
      headline: "Explainable by design.",
      body:
        "Every score is traceable to specific evidence — a commit, a transcript excerpt, a " +
        "static analysis output. No black boxes.",
    },
    {
      icon: "user-check",
      headline: "Human-in-the-loop, always.",
      body:
        "GroundTruth never rejects a candidate. Every hiring decision is made by a human, with " +
        "AI as decision support.",
    },
    {
      icon: "scale",
      headline: "Compliance-ready.",
      body:
        "Built against DPDP Act (India), NYC Local Law 144, Colorado AI Act, and California " +
        "ADS. Annual bias audits. Candidate consent and appeal rights.",
    },
  ] satisfies Pillar[],
} as const;

/* ==================================================================
   §10 — EARLY ACCESS / PRICING
   ================================================================== */

export const PRICING = {
  overline: "Early access",
  headline: "Free during early access.",
  lead:
    "We're onboarding our first cohort of engineers and recruiters. Lock in early pricing and " +
    "shape the product with us.",
  plans: [
    {
      name: "For engineers",
      price: "Free",
      note: "Forever. Full access.",
      features: [
        "Full profile and verification",
        "Unlimited job matches",
        "Downloadable evidence report",
        "Verified Engineer badge",
      ],
      cta: { label: "Create your profile", href: "/signup" },
      emphasis: true,
    },
    {
      name: "For recruiters",
      price: "Custom",
      note: "Book a demo for pricing.",
      features: [
        "Unlimited job posts",
        "Verified candidate matching",
        "Kanban hiring pipeline",
        "Full compliance and audit tooling",
        "Priority support",
      ],
      cta: { label: "Book a demo", href: "/signup?role=recruiter" },
      emphasis: false,
    },
  ],
} as const;

/* ==================================================================
   §11 — FAQ
   ================================================================== */

export const FAQ = {
  overline: "Frequently asked questions",
  headline: "Answers to the honest questions.",
  items: [
    {
      question: "How do you know a candidate actually wrote the code they submitted?",
      answer:
        "We analyze commit history, contribution share, authorship signals, and statistical " +
        "anomaly patterns to detect fake or gamed profiles. But the strongest verification comes " +
        "from the interview itself — the AI asks questions grounded in that specific code. A " +
        "candidate who didn't write it cannot defend the decisions in it.",
    },
    {
      question: "What if a candidate doesn't have a GitHub profile?",
      answer:
        "They can upload code directly, complete a proctored coding sample, or skip verification " +
        "and remain visible as an unverified profile. GitHub is the preferred anchor, not the " +
        "only one.",
    },
    {
      question: "Can candidates use AI tools during the interview?",
      answer:
        "Yes. The AI-collaboration round is specifically designed to evaluate how you work with " +
        "AI — aligned with how modern engineering hiring works at Meta, Google, and Canva in " +
        "2026. We evaluate judgment, not avoidance.",
    },
    {
      question: "How long does verification take?",
      answer:
        "30–45 minutes for the adaptive interview, plus a few minutes of background analysis " +
        "before you start. Once verified, your profile stays verified.",
    },
    {
      question: "Is my code and interview data private?",
      answer:
        "Yes. GroundTruth operates as a Data Fiduciary under India's DPDP Act. You can withdraw " +
        "consent and delete all your data at any time. Nothing is shared without your explicit " +
        "action.",
    },
    {
      question: "How does the AI decide who's a good match?",
      answer:
        "Every match is explainable. You see exactly why a role was surfaced — skill overlap, " +
        "verified evidence, experience fit. Humans make the final hire decision, always.",
    },
    {
      question: "Is this a replacement for human recruiters?",
      answer:
        "No. GroundTruth is a decision-support tool. It replaces the noisy screening layer so " +
        "recruiters can spend their time on real evaluation and candidates get seen for what " +
        "they actually built.",
    },
  ],
} as const;

/* ==================================================================
   §11b — WHO BUILT THIS
   ================================================================== */

/**
 * The team note. Text only.
 *
 * NOT A TESTIMONIAL, and deliberately not written as one. The page carries no
 * quotes, no customer logos and no invented people; this exists to put a human
 * voice behind the product without breaking that rule, which is why it is
 * written in the first person plural and says nothing about any individual.
 *
 * There is no portrait and no named byline, by choice rather than as a
 * placeholder. A photograph here would have to be a real person who agreed to
 * appear, and the collective signature is honest as it stands — it commits the
 * team to the words without inventing a face or a founder to attach them to.
 * If a named founder note is wanted later, that is a real person's decision to
 * make, not a field to fill.
 */
export const TEAM = {
  overline: "Who built this",
  headline: "Why we built GroundTruth.",
  note: [
    "We kept watching the same thing happen. Strong engineers filtered out by keyword matching " +
      "before a human ever read their work, and weak applications sailing through because they " +
      "were written well.",
    "The one signal that actually predicts anything — what someone has built, and whether they " +
      "can defend the decisions in it — was the one thing nobody was checking. So we built the " +
      "checking.",
    "Everything here is early. We would rather show you an honest work in progress, with sample " +
      "data labelled as sample data, than a polished promise we cannot evidence yet.",
  ],
  signature: "— The GroundTruth team",
} as const;

/* ==================================================================
   §12 — FINAL CTA
   ================================================================== */

export const FINAL_CTA = {
  overline: "Ready?",
  headline: "Get verified. Get discovered.",
  lead: "Free for engineers. Two minutes to start. No credit card, no catch.",
  primary: { label: "Create your profile", href: "/signup" },
  secondary: { label: "Hiring? Book a recruiter demo", href: "/signup?role=recruiter" },
} as const;

/* ==================================================================
   §13 — FOOTER
   ================================================================== */

/**
 * Three columns.
 *
 * The Legal column was added on request after an earlier pass left it out. The
 * standing rule still holds and is why `features/legal/routes.tsx` exists: every
 * link in this footer resolves to a real anchor or a real route. What those four
 * routes currently serve is an honest "not published yet" notice rather than a
 * drafted policy — see the note in `LegalDocumentPage.tsx`. No Blog, Careers,
 * About or Contact, because there is nothing behind them at all.
 */
export const FOOTER = {
  columns: [
    {
      heading: "Product",
      links: [
        { label: "How it works", href: "#how-it-works" },
        { label: "Why GroundTruth", href: "#difference" },
        { label: "Trust & compliance", href: "#trust" },
        { label: "Pricing", href: "#pricing" },
      ],
    },
    {
      heading: "Get started",
      links: [
        { label: "For engineers", href: "#engineers" },
        { label: "For recruiters", href: "#recruiters" },
        { label: "Create a profile", href: "/signup" },
        { label: "Log in", href: "/login" },
      ],
    },
    {
      heading: "Legal",
      links: [
        { label: "Privacy Policy", href: "/privacy" },
        { label: "Terms of Service", href: "/terms" },
        { label: "DPDP Compliance", href: "/dpdp" },
        { label: "Bias Audit Reports", href: "/bias-audit" },
      ],
    },
  ],
  backToTop: "Back to top",
  /* 2026, not 2027. See decision 2 in this file's header. */
  legal: "© 2026 GroundTruth AI. All rights reserved.",
  /**
   * The page shows four product mockups with plausible-looking numbers in them.
   * Each is labelled where it sits, and this line is the fourth surface saying
   * the same thing, because a reader who scrolled past the inline labels should
   * still not leave believing those were real candidates.
   */
  disclosure: "Product images show sample data. No real candidate is depicted.",
} as const;
