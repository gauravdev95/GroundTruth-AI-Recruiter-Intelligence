import {
  FileCode2,
  Github,
  GitBranch,
  Layers,
  MessageSquare,
  ScanSearch,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import type { PipelineStep } from "../types";

/** The eight-step candidate pipeline shown in the "How it works" section. */
export const PIPELINE_STEPS: PipelineStep[] = [
  { n: "01", t: "Profile Setup", d: "Candidate creates a profile and states the skills they claim.", I: UserRound },
  { n: "02", t: "GitHub Connection", d: "Secure OAuth link to the candidate's real repositories.", I: Github },
  { n: "03", t: "Repository Analysis", d: "Deterministic static pass over code, structure, and commit history.", I: GitBranch },
  { n: "04", t: "Skill Detection", d: "Skills detected from actual code and usage — not resume text.", I: ScanSearch },
  { n: "05", t: "Adaptive AI Interview", d: "Questions generated from the candidate's own commits and files.", I: MessageSquare },
  { n: "06", t: "Coding Profile", d: "Languages, frameworks, and patterns — each with a source reference.", I: FileCode2 },
  { n: "07", t: "Experience Evidence", d: "Individual contribution isolated via commit and diff analysis.", I: Layers },
  { n: "08", t: "Engineering Evidence Profile", d: "One explainable, evidence-backed profile recruiters can trust.", I: ShieldCheck },
];
