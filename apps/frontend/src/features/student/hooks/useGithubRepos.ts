import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { githubApi } from "../api/githubApi";

/** Redirects the whole page to GitHub's consent screen — not an XHR the
 * caller waits on. `mutate` is used only for its pending/error state while
 * the initial `GET /connect` call is in flight. */
export function useConnectGithub() {
  return useMutation({
    mutationFn: githubApi.connect,
    onSuccess: ({ authorize_url }) => {
      window.location.href = authorize_url;
    },
  });
}

/** 409 ("not connected yet") is an expected, common response — not a
 * transient failure — so this never retries. Callers branch on
 * `isError`/`error` to render "connect your account" instead of an error
 * banner. */
export function useGithubRepos(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.github.repos(),
    queryFn: githubApi.listRepos,
    enabled,
    retry: false,
  });
}

export function useSelectGithubRepos() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: githubApi.selectRepos,
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.studentProfile.section("projects"), result);
      queryClient.setQueryData(queryKeys.studentProfile.completeness(), result.completeness);
    },
  });
}
