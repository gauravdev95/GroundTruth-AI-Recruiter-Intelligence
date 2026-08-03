import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useAuthContext } from "@/features/auth/context/AuthContext";
import { queryKeys } from "@/lib/queryKeys";

import { RealtimeClient, type RealtimeMessage } from "../lib/realtimeClient";

/**
 * Opens the realtime socket for the signed-in user and turns each event into
 * a react-query cache invalidation.
 *
 * **It invalidates; it never writes.** A `NEW_MATCH` frame carries a job
 * title and a score — enough to *tell* the client something changed, nowhere
 * near enough to reconstruct a `MatchedJob` row (skill reasons, evidence
 * sources, company, deadline). Pushing the frame's contents into the feed
 * cache would create a second, thinner copy of data the server already owns,
 * and the two would drift the moment a match was rescored. Invalidating the
 * existing `studentFeed.jobs()` key means the socket only ever answers "now",
 * and the server stays the single source of what a match actually is.
 *
 * The `connected` frame is treated as a full invalidation for the same
 * reason there is no server-side replay buffer: a reconnecting client cannot
 * know what it missed, and refetching from the tables the notification rows
 * live in recovers all of it — a week's worth or a second's.
 */
export function useRealtimeEvents(): void {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const userId = user?.id ?? null;

  useEffect(() => {
    if (!userId) return;

    const invalidateAll = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentFeed.jobs() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all() });
      // The dashboard's "Job matches" tile counts the same rows, so leaving
      // it stale would show a feed and a count that disagree.
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentAnalytics.summary() });
    };

    const handle = (message: RealtimeMessage) => {
      switch (message.type) {
        case "connected":
          invalidateAll();
          break;
        case "new_match":
          invalidateAll();
          break;
        default:
          // Unknown event types are ignored rather than defaulting to a full
          // invalidation: a future server-side event this build has never
          // heard of should not silently refetch everything on every send.
          break;
      }
    };

    const client = new RealtimeClient(handle);
    client.connect();
    // Keyed on `userId`, so signing out and back in as someone else tears the
    // old socket down rather than leaving it bound to the previous account.
    return () => client.close();
  }, [queryClient, userId]);
}
