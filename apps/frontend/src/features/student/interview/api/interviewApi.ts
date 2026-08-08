import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/interview/schemas.py`. */

const BASE = "/student/interview";

export type InterviewStatus = "pending" | "in_progress" | "evaluating" | "completed" | "failed";

/** Where the *conversation* is, as distinct from where the record is. An
 * interview is `in_progress` for the whole of warmup, main and wrapup. */
export type InterviewStage = "warmup" | "main" | "wrapup" | "done";

export interface InterviewSummary {
  id: string;
  /** Null for a profile-grounded interview, which belongs to the candidate
   * rather than to any one repository. */
  project_id: string | null;
  status: InterviewStatus;
  stage: InterviewStage;
  question_count: number;
  current_question_index: number;
  time_limit_seconds: number;
  total_score: number | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface InterviewTurn {
  id: string;
  sequence: number;
  role: "interviewer" | "candidate";
  text: string;
  question_index: number | null;
  spoken_at: string;
}

export interface InterviewState {
  interview: InterviewSummary;
  transcript: InterviewTurn[];
  time_remaining_seconds: number;
  awaiting_candidate: boolean;
}

export interface DimensionScore {
  dimension: string;
  weight: number;
  score: number;
  evidence: string | null;
  /** 0-100, the same scale as `score` — see
   * `ai/interview_schema.py::DimensionScore.confidence`. */
  confidence: number;
}

export interface EvidenceReport {
  interview_id: string;
  project_id: string | null;
  total_score: number;
  rubric_weights: Record<string, number>;
  dimensions: DimensionScore[];
  transcript: InterviewTurn[];
  verified_claims: string[];
  contradicted_claims: string[];
  unsupported_claims: string[];
  strengths: string[];
  concerns: string[];
  summary: string;
  completed_at: string;
}

/**
 * The closed vocabulary of session-condition signals the room may report.
 * Mirrors `schemas.py::IntegrityEventType`; the server rejects anything else
 * with a 422, so a value invented here fails loudly rather than silently.
 *
 * Every name is an *observation*. None of them is a conclusion, and none of
 * them should ever be rendered to the candidate as one.
 */
export type IntegrityEventType =
  | "tab_hidden"
  | "window_blur"
  | "fullscreen_exit"
  | "camera_disabled"
  | "camera_unavailable"
  | "camera_obscured"
  | "microphone_disabled"
  | "microphone_unavailable"
  | "no_speech_detected"
  | "inactivity"
  | "connection_lost";

export interface IntegrityEvent {
  client_sequence: number;
  event_type: IntegrityEventType;
  elapsed_seconds: number;
  duration_seconds?: number | null;
  detail?: Record<string, string> | null;
}

export interface IntegritySummary {
  interview_id: string;
  counts: Partial<Record<IntegrityEventType, number>>;
  total: number;
  events: {
    event_type: IntegrityEventType;
    elapsed_seconds: number;
    duration_seconds: number | null;
    detail: Record<string, string> | null;
    recorded_at: string;
  }[];
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

  /** The socket's REST equivalent. Used when the WebSocket never came up —
   * see `interviewSocket.ts`; an interview that only works over a socket is
   * an interview some candidates simply cannot take. */
  submitTurn: async (interviewId: string, text: string): Promise<InterviewState> => {
    const res = await apiClient.post<InterviewState>(`${BASE}/${interviewId}/turns`, { text });
    return res.data;
  },

  getReport: async (interviewId: string): Promise<EvidenceReport> => {
    const res = await apiClient.get<EvidenceReport>(`${BASE}/${interviewId}/report`);
    return res.data;
  },

  recordIntegrity: async (
    interviewId: string,
    events: IntegrityEvent[],
  ): Promise<IntegritySummary> => {
    const res = await apiClient.post<IntegritySummary>(`${BASE}/${interviewId}/integrity`, {
      events,
    });
    return res.data;
  },

  getIntegrity: async (interviewId: string): Promise<IntegritySummary> => {
    const res = await apiClient.get<IntegritySummary>(`${BASE}/${interviewId}/integrity`);
    return res.data;
  },
};
