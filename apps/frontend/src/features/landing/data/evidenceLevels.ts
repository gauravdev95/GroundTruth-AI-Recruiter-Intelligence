import type { EvidenceLevel } from "../types";

/**
 * Levels 1–3 of the skill evidence scale. Level 4 ("Strong Evidence") has its
 * own layout in the Evidence section and isn't part of this list.
 */
export const EVIDENCE_LEVELS: EvidenceLevel[] = [
  {
    tag: "LEVEL 1 / 4",
    t: "Self-Reported",
    d: "The candidate has claimed the skill. A starting point — recorded, never trusted on its own.",
    on: 1,
  },
  {
    tag: "LEVEL 2 / 4",
    t: "Detected",
    d: "The skill appears in their actual code — specific files, commits, and usage found by repository analysis.",
    on: 2,
    cls: "lv2",
  },
  {
    tag: "LEVEL 3 / 4",
    t: "Interview-Consistent",
    d: "The candidate explains their own usage correctly under adaptive questioning about that exact code.",
    on: 3,
    cls: "lv3",
  },
];
