import { apiClient } from "@/lib/apiClient";

import type { DimensionScore, InterviewTurn } from "@/features/student/interview/api/interviewApi";
import type { VerificationStatus } from "@/features/student/api/profileApi";

/** Mirrors `apps/backend/src/domains/pipeline/evidence.py::build_evidence_record`
 * — deliberately a loosely-typed record (the backend explicitly documents it
 * as "read whatever's already there, narrate nothing"), typed just enough
 * for the evidence card to render each section safely. */
export interface EvidenceRecord {
  profile: {
    headline: string | null;
    college: string | null;
    degree: string | null;
    branch: string | null;
    graduation_year: number | null;
    location: string | null;
    target_role: string | null;
    profile_strength: number;
    is_discoverable: boolean;
  };
  github_account: {
    username: string;
    profile_url: string;
    verification_status: VerificationStatus;
    verification_score: number | null;
  } | null;
  projects: {
    title: string;
    repo_url: string | null;
    kind: string;
    technologies: string[];
    verification_status: VerificationStatus;
    verification_score: number | null;
    verification_payload: Record<string, unknown> | null;
  }[];
  coding_platform_accounts: {
    platform: string;
    handle: string;
    verification_status: VerificationStatus;
    verification_score: number | null;
    verification_payload: Record<string, unknown> | null;
  }[];
  certificates: {
    title: string;
    issuer: string;
    verification_status: VerificationStatus;
    verification_score: number | null;
  }[];
  experiences: {
    company_name: string;
    title: string;
    employment_type: string;
    verification_status: VerificationStatus;
  }[];
  skills: { name: string; proficiency: string; evidence_weight: number }[];
  interviews: {
    interview_id: string;
    project_title: string | null;
    total_score: number | null;
    completed_at: string | null;
    /** The narrative half of the report — what cannot be expressed as a
     * number. The scores and the conversation come as their own arrays below,
     * exactly as they are stored: the candidate's report and this record read
     * the same rows, so the two can never disagree. */
    evidence_report: {
      verified_claims: string[];
      contradicted_claims: string[];
      unsupported_claims: string[];
      strengths: string[];
      concerns: string[];
      summary: string;
    } | null;
    dimension_scores: DimensionScore[];
    transcript: Pick<InterviewTurn, "sequence" | "role" | "text" | "question_index">[];
  }[];
  match: {
    match_score: number;
    semantic_score: number;
    evidence_score: number;
    /** The stored `match_reasons` halves, under the names the read path uses
     * (`pipeline/evidence.py`). Each entry carries the concrete evidence that
     * backs the skill, which is what lets the drawer link a percentage to a
     * repository instead of asserting one. */
    matched_required_skills: EvidenceSkillReason[];
    matched_desirable_skills: EvidenceSkillReason[];
  } | null;
}

export interface EvidenceSkillReason {
  skill_name: string;
  candidate_has_skill: boolean;
  candidate_proficiency: string | null;
  evidence_weight: number | null;
  evidence_sources: {
    type: string;
    project_id?: string;
    title?: string;
    repo_url?: string | null;
    verification_score?: number | null;
  }[];
}

export const evidenceApi = {
  /**
   * `jobId` is what populates `record.match`, and therefore the drawer's
   * "Verified skills" section and its radar chart. Omit it only where there
   * is genuinely no job in scope (the standalone full-report page) — the
   * record then carries no match, which the UI renders as "no job context"
   * rather than as "no evidence".
   */
  getForCandidate: async (candidateProfileId: string, jobId?: string): Promise<EvidenceRecord> => {
    const res = await apiClient.get<{ record: EvidenceRecord }>(
      `/recruiter/candidates/${candidateProfileId}/evidence`,
      jobId ? { params: { job_posting_id: jobId } } : undefined,
    );
    return res.data.record;
  },
};
