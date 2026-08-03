import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/recruiter/schemas.py`. */

const BASE = "/recruiter/jobs";
const ASYNC_JOBS_BASE = "/jobs";

export type JobStatus = "draft" | "extracting" | "awaiting_confirmation" | "published" | "closed";
export type JobType = "full_time" | "part_time" | "internship" | "contract";
export type ExperienceLevel = "entry" | "mid" | "senior";
export type Proficiency = "novice" | "intermediate" | "advanced" | "expert";

export interface AsyncJobStatusResponse {
  id: string;
  job_type: string;
  status: "pending" | "running" | "succeeded" | "failed";
  attempts: number;
  error: string | null;
  is_dead_lettered: boolean;
}

export interface JobCreatePayload {
  title: string;
  description: string;
  job_type: JobType;
  experience_level: ExperienceLevel;
  location: string | null;
  is_remote: boolean;
  deadline: string | null;
}

export interface Job {
  id: string;
  company_id: string;
  title: string;
  description: string;
  job_type: JobType;
  experience_level: ExperienceLevel;
  location: string | null;
  is_remote: boolean;
  deadline: string | null;
  status: JobStatus;
  extraction_error: string | null;
  needs_reembedding: boolean;
  published_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractedSkill {
  name: string;
  min_proficiency: Proficiency;
}

export interface ExtractedRequirements {
  must_have_skills: ExtractedSkill[];
  desirable_skills: ExtractedSkill[];
  seniority: string;
  role_type: string | null;
  is_remote: boolean;
  location_constraints: string | null;
}

export interface JobRequirement {
  id: string;
  skill_id: string;
  skill_name: string;
  min_proficiency: Proficiency;
  is_required: boolean;
  weight: number;
}

export interface JobDetail {
  job: Job;
  extracted_requirements: ExtractedRequirements | null;
  requirements: JobRequirement[];
}

export interface JobSubmitAccepted {
  job: Job;
  async_job_id: string;
}

export interface RequirementSkillPayload {
  skill_name: string;
  min_proficiency: Proficiency;
  is_required: boolean;
  weight: number;
}

export interface ConfirmRequirementsPayload {
  seniority: string;
  skills: RequirementSkillPayload[];
}

export interface SkillMatchReason {
  skill_name: string;
  candidate_has_skill: boolean;
  candidate_proficiency: string | null;
  evidence_weight: number | null;
  evidence_sources: { type: string; title?: string; repo_url?: string | null; verification_score?: number | null }[];
}

export interface MatchedCandidate {
  match_score: number;
  semantic_score: number;
  evidence_score: number;
  matched_required_skills: SkillMatchReason[];
  matched_desirable_skills: SkillMatchReason[];
  /** First matched — "Matched {when}". Never moves. */
  computed_at: string;
  /** Last rescored — "Score updated {when}", shown only when it differs.
   * See `features/student/matches/components/MatchTimestamps`. */
  updated_at: string;
  candidate: {
    candidate_profile_id: string;
    headline: string | null;
    college: string | null;
    degree: string | null;
    branch: string | null;
    graduation_year: number | null;
    location: string | null;
    target_role: string | null;
    profile_strength: number;
  };
}

export interface MatchedCandidatesResponse {
  job_id: string;
  job_title: string;
  candidates: MatchedCandidate[];
}

export const jobsApi = {
  list: async (): Promise<Job[]> => {
    const res = await apiClient.get<{ jobs: Job[] }>(BASE);
    return res.data.jobs;
  },

  create: async (payload: JobCreatePayload): Promise<Job> => {
    const res = await apiClient.post<Job>(BASE, payload);
    return res.data;
  },

  get: async (jobId: string): Promise<JobDetail> => {
    const res = await apiClient.get<JobDetail>(`${BASE}/${jobId}`);
    return res.data;
  },

  update: async (jobId: string, payload: JobCreatePayload): Promise<Job> => {
    const res = await apiClient.put<Job>(`${BASE}/${jobId}`, payload);
    return res.data;
  },

  submit: async (jobId: string): Promise<JobSubmitAccepted> => {
    const res = await apiClient.post<JobSubmitAccepted>(`${BASE}/${jobId}/submit`);
    return res.data;
  },

  startRequirementEdit: async (jobId: string): Promise<JobDetail> => {
    const res = await apiClient.post<JobDetail>(`${BASE}/${jobId}/requirements/edit`);
    return res.data;
  },

  confirm: async (jobId: string, payload: ConfirmRequirementsPayload): Promise<JobDetail> => {
    const res = await apiClient.post<JobDetail>(`${BASE}/${jobId}/confirm`, payload);
    return res.data;
  },

  close: async (jobId: string): Promise<Job> => {
    const res = await apiClient.post<Job>(`${BASE}/${jobId}/close`);
    return res.data;
  },

  reopen: async (jobId: string): Promise<Job> => {
    const res = await apiClient.post<Job>(`${BASE}/${jobId}/reopen`);
    return res.data;
  },

  getMatches: async (jobId: string): Promise<MatchedCandidatesResponse> => {
    const res = await apiClient.get<MatchedCandidatesResponse>(`${BASE}/${jobId}/matches`);
    return res.data;
  },

  getAsyncJob: async (asyncJobId: string): Promise<AsyncJobStatusResponse> => {
    const res = await apiClient.get<AsyncJobStatusResponse>(`${ASYNC_JOBS_BASE}/${asyncJobId}`);
    return res.data;
  },
};
