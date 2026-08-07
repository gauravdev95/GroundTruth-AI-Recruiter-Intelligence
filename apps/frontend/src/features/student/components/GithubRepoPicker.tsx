import { isAxiosError } from "axios";
import { GitFork, Github, Loader2, Star } from "lucide-react";
import { useState } from "react";

import { Button, Modal, Skeleton, useToast } from "@/components";

import { useConnectGithub, useGithubRepos, useSelectGithubRepos } from "../hooks/useGithubRepos";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";

const MAX_REPOS = 3;

interface GithubRepoPickerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * "Import from GitHub" — connect (if needed) then pick up to 3 repositories.
 * Selecting writes them through the ordinary projects section save, so they
 * go through the exact same reconciliation and verification queueing a
 * hand-typed repo URL does (`domains/student/service.py::set_projects_from_github`).
 */
export function GithubRepoPicker({ open, onClose }: GithubRepoPickerProps) {
  const [selected, setSelected] = useState<string[]>([]);
  const { showToast } = useToast();

  const connect = useConnectGithub();
  const repos = useGithubRepos(open);
  const select = useSelectGithubRepos();

  const needsConnect = repos.isError && isAxiosError(repos.error) && repos.error.response?.status === 409;

  function toggle(fullName: string) {
    setSelected((current) => {
      if (current.includes(fullName)) return current.filter((name) => name !== fullName);
      if (current.length >= MAX_REPOS) return current;
      return [...current, fullName];
    });
  }

  function handleClose() {
    setSelected([]);
    onClose();
  }

  function handleImport() {
    select.mutate(selected, {
      onSuccess: () => {
        showToast(`Imported ${selected.length} repositor${selected.length === 1 ? "y" : "ies"} for verification.`, "success");
        handleClose();
      },
    });
  }

  return (
    <Modal open={open} onClose={handleClose} title="Import from GitHub" className="max-w-lg">
      {needsConnect ? (
        <div className="space-y-4 text-center">
          <p className="text-sm text-[var(--slate)]">
            Connect your GitHub account to pick repositories directly, instead of pasting URLs one at a
            time.
          </p>
          <Button
            type="button"
            onClick={() => connect.mutate()}
            isLoading={connect.isPending}
            disabled={connect.isPending}
          >
            <Github size={16} aria-hidden="true" /> Connect GitHub
          </Button>
          {connect.isError ? (
            <p role="alert" className="text-xs text-[var(--failed)]">
              {getProfileErrorMessage(connect.error, "Could not start the GitHub connection.")}
            </p>
          ) : null}
        </div>
      ) : repos.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : repos.isError ? (
        <p role="alert" className="text-sm text-[var(--failed)]">
          {getProfileErrorMessage(repos.error, "Could not load your repositories.")}
        </p>
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-[var(--slate)]">
            Select up to {MAX_REPOS}. This replaces your currently linked repository projects.
          </p>
          <ul className="max-h-80 space-y-2 overflow-y-auto">
            {repos.data?.map((repo) => {
              const checked = selected.includes(repo.full_name);
              const disabled = !checked && selected.length >= MAX_REPOS;
              return (
                <li key={repo.full_name}>
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition ${
                      checked ? "border-[var(--rule)] bg-[var(--panel)]" : "border-[var(--rule)] bg-[var(--panel)]"
                    } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={checked}
                      disabled={disabled}
                      onChange={() => toggle(repo.full_name)}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-1.5 truncate text-sm font-medium text-[var(--ink)]">
                        {repo.full_name}
                        {repo.fork ? <GitFork size={12} className="shrink-0 text-[var(--muted)]" aria-hidden="true" /> : null}
                      </p>
                      {repo.description ? (
                        <p className="mt-0.5 truncate text-xs text-[var(--slate)]">{repo.description}</p>
                      ) : null}
                      <p className="mt-1 flex items-center gap-3 text-xs text-[var(--muted)]">
                        {repo.language ? <span>{repo.language}</span> : null}
                        <span className="flex items-center gap-1">
                          <Star size={11} aria-hidden="true" /> {repo.stargazers_count}
                        </span>
                      </p>
                    </div>
                  </label>
                </li>
              );
            })}
            {repos.data?.length === 0 ? (
              <p className="py-6 text-center text-sm text-[var(--slate)]">No repositories found.</p>
            ) : null}
          </ul>

          {select.isError ? (
            <p role="alert" className="text-xs text-[var(--failed)]">
              {getProfileErrorMessage(select.error, "Could not import the selected repositories.")}
            </p>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={selected.length === 0 || select.isPending}
              onClick={handleImport}
            >
              {select.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
              Import {selected.length > 0 ? `(${selected.length})` : ""}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
