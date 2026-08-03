import { apiClient } from "@/lib/apiClient";

import type { ProjectsSection, SectionEnvelope } from "./profileApi";

/** Types mirror `apps/backend/src/domains/student/github_router.py`. */

const BASE = "/student/github";

export interface GithubRepo {
  full_name: string;
  name: string;
  description: string | null;
  language: string | null;
  fork: boolean;
  private: boolean;
  stargazers_count: number;
  updated_at: string | null;
}

export const githubApi = {
  /** Returns the GitHub authorize URL — the caller does a full-page
   * navigation to it (`window.location.href = ...`), it is not fetched via
   * axios/XHR. */
  connect: async (): Promise<{ authorize_url: string }> => {
    const res = await apiClient.get<{ authorize_url: string }>(`${BASE}/connect`);
    return res.data;
  },

  listRepos: async (): Promise<GithubRepo[]> => {
    const res = await apiClient.get<{ repos: GithubRepo[] }>(`${BASE}/repos`);
    return res.data.repos;
  },

  selectRepos: async (repoFullNames: string[]): Promise<SectionEnvelope<ProjectsSection>> => {
    const res = await apiClient.post<SectionEnvelope<ProjectsSection>>(`${BASE}/repos/select`, {
      repo_full_names: repoFullNames,
    });
    return res.data;
  },
};
