import { apiClient } from "@/lib/apiClient";

import type {
  BasicInfoPayload,
  CertificatesPayload,
  ExperiencesPayload,
  ProfileCompleteness,
  ProjectsPayload,
  TechnicalPayload,
} from "../../api/profileApi";

/**
 * Types mirror `apps/backend/src/domains/resume/schemas.py`.
 *
 * The confirm payload reuses the section payload types from `profileApi` —
 * the backend reuses the section *request schemas* for the same reason, so the
 * two stay in step by construction rather than by discipline.
 */

const BASE = "/student/resume";
const JOBS_BASE = "/jobs";

export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export interface JobStatusResponse {
  id: string;
  job_type: string;
  status: JobStatus;
  attempts: number;
  error: string | null;
  result: Record<string, unknown> | null;
  /** Retries exhausted. Distinguishes "gave up" from "still backing off". */
  is_dead_lettered: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export type ResumeUploadStatus = "uploaded" | "processing" | "extracted" | "failed";

export interface ResumeUpload {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: ResumeUploadStatus;
  async_job_id: string | null;
  error: string | null;
  created_at: string;
}

export interface ResumeUploadAccepted {
  upload: ResumeUpload;
  async_job_id: string;
}

export type DraftStatus = "pending_review" | "confirmed" | "discarded";

export interface ResumeDraft {
  id: string;
  resume_upload_id: string;
  status: DraftStatus;
  provider: string;
  model: string;
  payload: Record<string, unknown>;
  confirmed_at: string | null;
  created_at: string;
}

/** Server-mapped, section-shaped suggestions. Partial by design — `unmapped`
 * lists what the resume could not supply rather than guessing it. */
export interface DraftSuggestions {
  basic: Partial<BasicInfoPayload>;
  technical: Partial<TechnicalPayload>;
  projects: ProjectsPayload["projects"];
  certificates: CertificatesPayload["certificates"];
  experience: ExperiencesPayload["experiences"];
  unmapped: string[];
}

export interface ResumeDraftDetail {
  draft: ResumeDraft;
  suggestions: DraftSuggestions;
}

/** Every section optional: a student may confirm only what they trust. */
export interface ConfirmDraftPayload {
  basic?: BasicInfoPayload;
  technical?: TechnicalPayload;
  projects?: ProjectsPayload;
  certificates?: CertificatesPayload;
  experience?: ExperiencesPayload;
}

export interface ConfirmDraftResponse {
  draft: ResumeDraft;
  completeness: ProfileCompleteness;
}

export const resumeApi = {
  /**
   * `onProgress` reports transfer percent 0-100, which is the only part of the
   * flow with a real denominator. Everything after the 202 — parsing, the LLM
   * call — has no measurable total, so the UI switches to an indeterminate
   * "Analyzing…" state rather than inventing a second progress bar.
   */
  upload: async (
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<ResumeUploadAccepted> => {
    const form = new FormData();
    form.append("file", file);
    // Content-Type is deliberately unset so the browser adds the multipart
    // boundary; the client's JSON default would produce an unparseable body.
    const res = await apiClient.post<ResumeUploadAccepted>(`${BASE}/uploads`, form, {
      headers: { "Content-Type": undefined },
      onUploadProgress: onProgress
        ? (event) => {
            // `total` is absent on some proxies and in some browsers. Reporting
            // a bogus percent would be worse than reporting none, so skip.
            if (!event.total) return;
            onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
          }
        : undefined,
    });
    return res.data;
  },

  listUploads: async (): Promise<{ uploads: ResumeUpload[] }> => {
    const res = await apiClient.get<{ uploads: ResumeUpload[] }>(`${BASE}/uploads`);
    return res.data;
  },

  deleteUpload: async (uploadId: string): Promise<void> => {
    await apiClient.delete(`${BASE}/uploads/${uploadId}`);
  },

  getDraftForUpload: async (uploadId: string): Promise<ResumeDraftDetail> => {
    const res = await apiClient.get<ResumeDraftDetail>(`${BASE}/uploads/${uploadId}/draft`);
    return res.data;
  },

  confirmDraft: async (
    draftId: string,
    payload: ConfirmDraftPayload,
  ): Promise<ConfirmDraftResponse> => {
    const res = await apiClient.post<ConfirmDraftResponse>(
      `${BASE}/drafts/${draftId}/confirm`,
      payload,
    );
    return res.data;
  },

  discardDraft: async (draftId: string): Promise<ResumeDraft> => {
    const res = await apiClient.post<ResumeDraft>(`${BASE}/drafts/${draftId}/discard`);
    return res.data;
  },

  getJob: async (jobId: string): Promise<JobStatusResponse> => {
    const res = await apiClient.get<JobStatusResponse>(`${JOBS_BASE}/${jobId}`);
    return res.data;
  },
};
