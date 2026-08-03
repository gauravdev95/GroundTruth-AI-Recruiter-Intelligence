import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { notificationsApi } from "../api/notificationsApi";

/** Still polled, now *also* pushed.
 *
 * `features/realtime` invalidates this key the moment a notification is
 * written, so the bell normally updates immediately. The 30s poll stays as
 * the floor underneath it: realtime delivery is best-effort by design
 * (`src/realtime/__init__.py`), and a client whose socket died without
 * either side noticing must still converge. Removing the poll would make a
 * silently-dead socket indistinguishable from a quiet inbox. */
export function useNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications.all(),
    queryFn: notificationsApi.list,
    refetchInterval: 30_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: notificationsApi.markRead,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all() }),
  });
}
