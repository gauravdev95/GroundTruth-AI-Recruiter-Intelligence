import { useQuery } from "@tanstack/react-query";

import { fetchActivityFeed, type ActivityFeed } from "../api/activityApi";

/**
 * Polls the analysis feed while work is in flight, and stops when it is not.
 *
 * THE POLLING CONTRACT
 *
 * `refetchInterval` reads `is_running` off the last response rather than
 * tracking state locally. That single detail is what guarantees the poll
 * cannot outlive the work: the server decides when it is finished, and the
 * client has no independent opinion that could disagree and keep polling a
 * settled profile forever.
 *
 * `POLL_MS` is 2500. Fast enough that a stage completing feels immediate —
 * under the ~3s threshold where a user starts wondering whether the screen
 * is stuck — and slow enough that a student with twelve claims running for
 * two minutes costs under fifty requests. A one-second poll would have
 * looked marginally more alive and tripled the load for no perceptible gain,
 * because the underlying stages take seconds to tens of seconds each.
 *
 * `refetchOnWindowFocus` is left on. A student who tabs away for a minute
 * and comes back should see current state on the first frame, not on the
 * next tick.
 */
const POLL_MS = 2500;

export function useActivityFeed(options: { enabled?: boolean } = {}) {
  const { enabled = true } = options;

  return useQuery<ActivityFeed>({
    queryKey: ["student", "onboarding", "activity"],
    queryFn: fetchActivityFeed,
    enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      // No data yet — keep polling; this is the initial load, not a settled
      // state. Returning false here would strand a slow first response.
      if (!data) return POLL_MS;
      return data.is_running ? POLL_MS : false;
    },
    // The feed is a live status readout: showing a cached snapshot from a
    // previous visit as though it were current would misreport what the
    // workers are doing right now.
    staleTime: 0,
  });
}
