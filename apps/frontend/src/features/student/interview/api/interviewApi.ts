import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/interview/schemas.py`. */

const BASE = "/student/interview";

export type InterviewStatus = "pending" | "in_progress" | "evaluating" | "completed" | "failed";

export interface InterviewSummary {
  id: string;
  project_id: string;
  status: InterviewStatus;
  question_count: number;
  total_score: number | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface InterviewQuestion {
  id: string;
  sequence: number;
  prompt: string;
  time_limit_seconds: number;
  presented_at: string | null;
  is_answered: boolean;
}

export interface InterviewState {
  interview: InterviewSummary;
  current_question: InterviewQuestion | null;
  answered_count: number;
}

export interface DimensionScore {
  dimension: string;
  weight: number;
  score: number;
  rationale: string | null;
}

export interface AnsweredQuestionReport {
  sequence: number;
  prompt: string;
  grounded_in: { description?: string } | null;
  transcript: string;
  time_taken_seconds: number | null;
  exceeded_time_limit: boolean;
  scores: DimensionScore[];
  weighted_score: number;
}

export interface EvidenceReport {
  interview_id: string;
  project_id: string;
  total_score: number;
  rubric_weights: Record<string, number>;
  questions: AnsweredQuestionReport[];
  completed_at: string;
}

export const interviewApi = {
  start: async (projectId: string): Promise<InterviewSummary> => {
    const res = await apiClient.post<InterviewSummary>(`${BASE}/projects/${projectId}/start`);
    return res.data;
  },

  latestForProject: async (projectId: string): Promise<InterviewSummary> => {
    const res = await apiClient.get<InterviewSummary>(`${BASE}/projects/${projectId}/latest`);
    return res.data;
  },

  getState: async (interviewId: string): Promise<InterviewState> => {
    const res = await apiClient.get<InterviewState>(`${BASE}/${interviewId}`);
    return res.data;
  },

  submitAnswer: async (
    interviewId: string,
    questionId: string,
    payload: { transcript: string; time_taken_seconds: number },
  ): Promise<InterviewState> => {
    const res = await apiClient.post<InterviewState>(
      `${BASE}/${interviewId}/questions/${questionId}/answer`,
      payload,
    );
    return res.data;
  },

  getReport: async (interviewId: string): Promise<EvidenceReport> => {
    const res = await apiClient.get<EvidenceReport>(`${BASE}/${interviewId}/report`);
    return res.data;
  },
};
