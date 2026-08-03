import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { notesApi } from "../api/notesApi";

export function useNotes(applicationId: string) {
  return useQuery({
    queryKey: queryKeys.pipeline.notes(applicationId),
    queryFn: () => notesApi.list(applicationId),
    enabled: Boolean(applicationId),
  });
}

export function useAddNote(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => notesApi.add(applicationId, body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.notes(applicationId) }),
  });
}
