import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { matchesApi } from "../api/matchesApi";

export function useJobFeed() {
  return useQuery({ queryKey: queryKeys.studentFeed.jobs(), queryFn: matchesApi.getFeed });
}
