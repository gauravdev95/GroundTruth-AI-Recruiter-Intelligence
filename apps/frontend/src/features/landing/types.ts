import type { LucideIcon } from "lucide-react";

export interface PipelineStep {
  n: string;
  t: string;
  d: string;
  I: LucideIcon;
}

export interface EvidenceLevel {
  tag: string;
  t: string;
  d: string;
  on: number;
  cls?: string;
}

export interface RecruiterStep {
  n: string;
  t: string;
  s: string;
  I: LucideIcon;
}

export interface CandidateRow {
  i: string;
  n: string;
  sc: number;
  sk: string[];
  ev: number;
}

export interface TechBadge {
  t: string;
  I: LucideIcon;
}

export interface TeamMember {
  i: string;
  n: string;
  r: string;
}

export interface HeroFragment {
  t: string;
  cls: "minus" | "plus";
  tx: string;
  ty: string;
  d: string;
}

export interface HeroDot {
  tx: string;
  ty: string;
  d: string;
}
