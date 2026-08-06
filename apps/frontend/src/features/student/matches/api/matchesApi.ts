import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/matching/schemas.py`. */

const BASE = "/student/matches";

export interface SkillMatchReason {
  skill_name: string;
  candidate_has_skill: boolean;
  candidate_proficiency: string | null;
  evidence_weight: number | null;
  evidence_sources: { type: string; title?: string; repo_url?: string | null }[];
}

/** Mirrors `matching/tiers.py::MatchTier`. Tier B is the only one the
 * student-facing UI names, and it names it "High Match" — never "Tier B". */
export type MatchTier = "discoverable" | "smart_apply_recommended";

export interface MatchedJob {
  match_score: number;
  semantic_score: number;
  evidence_score: number;
  matched_required_skills: SkillMatchReason[];
  matched_desirable_skills: SkillMatchReason[];
  /** When this pair first matched — rendered as "Matched {when}". Never moves. */
  computed_at: string;
  /** When the score was last recomputed — rendered as "Score updated {when}",
   * and only when it differs from `computed_at`. See `MatchTimestamps`. */
  updated_at: string;
  /** Derived per request from this job's whole pool, never stored. `null` for
   * a pair below Tier A's floor. */
  tier: MatchTier | null;
  /** One sentence composed from stored evidence — not model-written. */
  reasoning: string;
  job: {
    job_id: string;
    title: string;
    company_name: string;
    job_type: string;
    experience_level: string;
    location: string | null;
    is_remote: boolean;
    deadline: string | null;
    description: string;
  };
}

export const matchesApi = {
  getFeed: async (): Promise<MatchedJob[]> => {
    const res = await apiClient.get<{ jobs: MatchedJob[] }>(BASE);
    return res.data.jobs;
  },
};
