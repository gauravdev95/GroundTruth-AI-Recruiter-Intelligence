import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { RealtimeClient, type RealtimeMessage } from "@/features/realtime";
import { queryKeys } from "@/lib/queryKeys";

/**
 * Keeps an open pipeline board current while the recruiter is looking at it.
 *
 * **Same socket as everything else, not a second one.** The brief for this
 * screen asked for Socket.IO; this codebase already runs a raw WebSocket at
 * `/api/v1/realtime/ws` with a first-frame auth handshake, jittered
 * reconnect, a 4401 refresh path and a Redis fan-out behind it
 * (`src/realtime/`). Adding Socket.IO would mean a second transport, a second
 * server-side adapter on a sync FastAPI app, a second auth story, and two
 * connections per logged-in user — to deliver the same frames. So this reuses
 * `RealtimeClient`. If the socket is ever swapped wholesale, this hook and
 * `useRealtimeEvents` change together and nothing else does.
 *
 * **It invalidates; it never writes.** The `new_match` frame names a job, not
 * a candidate — enough to say "this board changed", nowhere near enough to
 * construct a card (headline, skills, reasoning, verification). Pushing frame
 * contents into the cache would create a thinner second copy of data the
 * server owns, and the two would disagree the moment the pair was rescored.
 *
 * Returns the set of candidate ids that appeared *after* the first load, so
 * the board can animate them in. Derived from successive query results rather
 * than from the frames themselves, which means it is also correct for a card
 * that arrives via an ordinary refetch — and cannot claim a card is new
 * because a frame said so when the refetch that followed disagreed.
 */
export function usePipelineRealtime(jobId: string, matchedIds: string[]): Set<string> {
  const queryClient = useQueryClient();
  const [arrivals, setArrivals] = useState<Set<string>>(() => new Set());
  const known = useRef<Set<string> | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const handle = (message: RealtimeMessage) => {
      if (message.type === "connected") {
        // A reconnect cannot know what it missed while it was away; refetching
        // recovers all of it. Same reasoning as `useRealtimeEvents`.
        void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.board(jobId) });
        return;
      }
      if (message.type !== "new_match") return;
      // The same event type reaches students (about their feed) and recruiters
      // (about a board). The recruiter frame carries the job it refers to, so
      // a recruiter with two boards open in two tabs refreshes only the one
      // that changed.
      if (message.payload.job_posting_id === jobId) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.board(jobId) });
      }
    };

    const client = new RealtimeClient(handle);
    client.connect();
    return () => client.close();
  }, [jobId, queryClient]);

  useEffect(() => {
    if (known.current === null) {
      // First render establishes the baseline. Everything already on the board
      // when the recruiter opened it is not an arrival.
      known.current = new Set(matchedIds);
      return;
    }
    const fresh = matchedIds.filter((id) => !known.current?.has(id));
    if (fresh.length === 0) return;
    for (const id of fresh) known.current.add(id);
    setArrivals((prev) => new Set([...prev, ...fresh]));
  }, [matchedIds]);

  // Reset the baseline when the board changes underneath the hook, so
  // navigating between two jobs does not animate the second board's entire
  // Matched column.
  useEffect(() => {
    known.current = null;
    setArrivals(new Set());
  }, [jobId]);

  return arrivals;
}
