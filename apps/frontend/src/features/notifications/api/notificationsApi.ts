import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/pipeline/schemas.py`. Shared by
 * both roles — a notification's `user_id` already scopes it server-side,
 * so one client serves the candidate bell and the recruiter bell alike. */

const BASE = "/notifications";

export type NotificationType = "stage_change" | "new_message";

export interface Notification {
  id: string;
  type: NotificationType;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface NotificationList {
  notifications: Notification[];
  unread_count: number;
}

export const notificationsApi = {
  list: async (): Promise<NotificationList> => {
    const res = await apiClient.get<NotificationList>(BASE);
    return res.data;
  },
  markRead: async (notificationId: string): Promise<Notification> => {
    const res = await apiClient.post<Notification>(`${BASE}/${notificationId}/read`);
    return res.data;
  },
};
