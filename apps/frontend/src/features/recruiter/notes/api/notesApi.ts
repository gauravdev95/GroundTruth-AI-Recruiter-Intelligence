import { apiClient } from "@/lib/apiClient";

/** Mirrors `apps/backend/src/domains/pipeline/schemas.py`. Scoped to the
 * recruiter's own company at the query layer server-side
 * (`domains/pipeline/notes.py`) — never rendered anywhere a candidate can
 * reach, and this component always says so visibly. */
export interface Note {
  id: string;
  application_id: string;
  author_user_id: string | null;
  body: string;
  created_at: string;
}

const base = (applicationId: string) => `/recruiter/applications/${applicationId}/notes`;

export const notesApi = {
  list: async (applicationId: string): Promise<Note[]> => {
    const res = await apiClient.get<Note[]>(base(applicationId));
    return res.data;
  },
  add: async (applicationId: string, body: string): Promise<Note> => {
    const res = await apiClient.post<Note>(base(applicationId), { body });
    return res.data;
  },
};
