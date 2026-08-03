import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/pipeline/schemas.py`. The two
 * roles read/write the same conversation through different URL prefixes
 * (`/student/applications/{id}/messages` vs
 * `/recruiter/applications/{id}/messages`) — same ownership-checked
 * `Application` underneath, so this factory takes the prefix rather than
 * duplicating the client per role. */

export interface Message {
  id: string;
  sender_user_id: string | null;
  body: string;
  created_at: string;
}

export interface Conversation {
  application_id: string;
  messages: Message[];
}

export function createMessagingApi(rolePrefix: "student" | "recruiter") {
  const base = (applicationId: string) => `/${rolePrefix}/applications/${applicationId}/messages`;

  return {
    list: async (applicationId: string): Promise<Conversation> => {
      const res = await apiClient.get<Conversation>(base(applicationId));
      return res.data;
    },
    send: async (applicationId: string, body: string): Promise<Message> => {
      const res = await apiClient.post<Message>(base(applicationId), { body });
      return res.data;
    },
  };
}
