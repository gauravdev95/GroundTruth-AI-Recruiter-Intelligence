import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { createMessagingApi } from "../api/messagingApi";

export function useConversation(rolePrefix: "student" | "recruiter", applicationId: string) {
  const api = createMessagingApi(rolePrefix);
  return useQuery({
    queryKey: queryKeys.applications.messages(applicationId),
    queryFn: () => api.list(applicationId),
    enabled: Boolean(applicationId),
    // Cheap poll so a reply shows up without a manual refresh — same
    // rationale as the notification bell.
    refetchInterval: 15_000,
  });
}

export function useSendMessage(rolePrefix: "student" | "recruiter", applicationId: string) {
  const api = createMessagingApi(rolePrefix);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => api.send(applicationId, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.applications.messages(applicationId) }),
  });
}
