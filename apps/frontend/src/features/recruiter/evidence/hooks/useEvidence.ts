import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { evidenceApi } from "../api/evidenceApi";

export function useCandidateEvidence(candidateProfileId: string) {
  return useQuery({
    queryKey: queryKeys.evidence.candidate(candidateProfileId),
    queryFn: () => evidenceApi.getForCandidate(candidateProfileId),
    enabled: Boolean(candidateProfileId),
  });
}
