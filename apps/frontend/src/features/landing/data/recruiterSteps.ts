import { ArrowUpDown, Database, ListChecks, Sparkles, Upload, Users } from "lucide-react";

import type { RecruiterStep } from "../types";

/** The six-step recruiter workflow, from job description to shortlist. */
export const RECRUITER_STEPS: RecruiterStep[] = [
  { n: "01", t: "Upload JD", s: "job description in", I: Upload },
  { n: "02", t: "AI Skill Extraction", s: "required skills parsed", I: Sparkles },
  { n: "03", t: "Review & Verify", s: "recruiter stays in control", I: ListChecks },
  { n: "04", t: "Hybrid Search", s: "PostgreSQL + pgvector", I: Database },
  { n: "05", t: "Similarity Ranking", s: "evidence-weighted", I: ArrowUpDown },
  { n: "06", t: "Top-K Shortlist", s: "ready to interview", I: Users },
];
