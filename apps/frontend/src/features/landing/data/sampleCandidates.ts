import type { CandidateRow } from "../types";

/** Demo-only ranked candidates shown in the recruiter shortlist table. */
export const SAMPLE_CANDIDATES: CandidateRow[] = [
  { i: "AS", n: "Ananya Sharma", sc: 0.94, sk: ["Python", "FastAPI", "Celery"], ev: 12 },
  { i: "RV", n: "Rohit Verma", sc: 0.91, sk: ["TypeScript", "Next.js"], ev: 9 },
  { i: "PN", n: "Priya Nair", sc: 0.87, sk: ["PostgreSQL", "pgvector"], ev: 7 },
  { i: "AM", n: "Arjun Mehta", sc: 0.83, sk: ["Docker", "CI/CD"], ev: 5 },
];
