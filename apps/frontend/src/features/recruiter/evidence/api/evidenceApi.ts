import { apiClient } from "@/lib/apiClient";

import type { EvidenceReport } from "@/features/student/interview/api/interviewApi";
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
    evidence_report: EvidenceReport | null;
  }[];
  match: {
    match_score: number;
    semantic_score: number;
    evidence_score: number;
  } | null;
}

export const evidenceApi = {
  getForCandidate: async (candidateProfileId: string): Promise<EvidenceRecord> => {
    const res = await apiClient.get<{ record: EvidenceRecord }>(`/recruiter/candidates/${candidateProfileId}/evidence`);
    return res.data.record;
  },
};
