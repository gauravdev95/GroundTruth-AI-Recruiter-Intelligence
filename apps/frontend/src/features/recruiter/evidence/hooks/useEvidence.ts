import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { evidenceApi } from "../api/evidenceApi";

export function useCandidateEvidence(candidateProfileId: string, jobId?: string) {
  return useQuery({
    queryKey: queryKeys.evidence.candidate(candidateProfileId, jobId),
    queryFn: () => evidenceApi.getForCandidate(candidateProfileId, jobId),
    enabled: Boolean(candidateProfileId),
  });
}
