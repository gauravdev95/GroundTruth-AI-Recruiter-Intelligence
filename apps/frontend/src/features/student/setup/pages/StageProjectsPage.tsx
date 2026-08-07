import { isAxiosError } from "axios";
import { GitFork, Star } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, Skeleton, useToast } from "@/components";
import { cn } from "@/lib/utils";

import { useGithubRepos, useSelectGithubRepos } from "../../hooks/useGithubRepos";
import { useProjectsSection, useSaveProjects } from "../../hooks/useProfileSection";
import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { MAX_CONTRIBUTION_CHARS } from "../../schemas/profileSchemas";
import { StageShell } from "../components/StageShell";
import { useStageNav } from "../hooks/useStageNav";
import { stageByStepKey } from "../lib/stages";

const STAGE = stageByStepKey("projects")!;
const MAX_REPOS = 3;

/**
 * Stage 3 — link 1 to 3 repositories. Mandatory.
 *
 * **This is where the background pipeline starts.** Selecting repositories
 * POSTs to `/student/github/repos/select`, which writes them through the
 * ordinary projects service and queues verification for each — fork detection,
 * contribution analysis, static analysis, interview-question generation. That
 * happens the moment the first repository is confirmed, not at submit, so the
 * analysis runs underneath the three optional stages that follow instead of
 * after them. Nothing on this screen waits for it.
 *
 * Adding a second or third repository later re-queues to include it; the
 * service skips anything already looked at, so re-selecting is not re-running.
 *
 * **The contribution note is saved separately, and only if written.** The repo
 * selection endpoint owns which repositories are linked; the note is a
 * `description` on the resulting project rows, so it goes through the ordinary
 * projects PUT afterwards. Splitting it that way keeps the selection call
 * idempotent — a student who edits only their note does not re-queue the
 * pipeline.
 */
export function StageProjectsPage() {
  const { advance, goBack } = useStageNav();
  const { showToast } = useToast();

  const repos = useGithubRepos(true);
  const projects = useProjectsSection();
  const select = useSelectGithubRepos();
  const saveProjects = useSaveProjects();

  const [selected, setSelected] = useState<string[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const linked = projects.data?.data.projects ?? [];

  // Seeded from the server once the section loads, so a student returning to
  // this stage sees what they already linked rather than an empty picker.
  // Keyed on the linked set, not on mount: the selection endpoint rewrites
  // these rows, and re-seeding after it lands is what keeps the two in step.
  useEffect(() => {
    if (linked.length === 0) return;
    setSelected(linked.map((project) => repoFullName(project.repo_url)).filter((v): v is string => v !== null));
    setNotes(
      Object.fromEntries(
        linked
          .map((project) => [repoFullName(project.repo_url), project.description ?? ""])
          .filter(([key]) => key !== null) as [string, string][],
      ),
    );
  }, [projects.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const needsConnect =
    repos.isError && isAxiosError(repos.error) && repos.error.response?.status === 409;

  function toggle(fullName: string) {
    setSelected((current) => {
      if (current.includes(fullName)) return current.filter((name) => name !== fullName);
      if (current.length >= MAX_REPOS) return current;
      return [...current, fullName];
    });
  }

  async function onContinue() {
    // Already linked and unchanged: nothing to write, so advance without
    // re-queueing an analysis that is running or done.
    const unchanged =
      selected.length === linked.length &&
      selected.every((name) => linked.some((project) => repoFullName(project.repo_url) === name));

    const result = unchanged ? { data: { projects: linked } } : await select.mutateAsync(selected);

    const written = result.data.projects;
    const noteChanged = written.some(
      (project) => (project.description ?? "") !== (notes[repoFullName(project.repo_url) ?? ""] ?? ""),
    );

    if (noteChanged) {
      await saveProjects.mutateAsync({
        projects: written.map((project) => ({
          kind: project.kind,
          title: project.title,
          description: notes[repoFullName(project.repo_url) ?? ""] || null,
          repo_url: project.repo_url,
          live_demo_url: project.live_demo_url,
          is_primary: project.is_primary,
          claimed_technologies: project.claimed_technologies,
        })),
      });
    }

    showToast(
      `${selected.length} project${selected.length === 1 ? "" : "s"} linked. We've started analysing them.`,
      "success",
    );
    advance();
  }

  const busy = select.isPending || saveProjects.isPending;
  const error = select.isError
    ? getProfileErrorMessage(select.error, "Could not link those repositories.")
    : saveProjects.isError
      ? getProfileErrorMessage(saveProjects.error, "Linked, but your notes did not save.")
      : null;

  return (
    <StageShell
      stage={STAGE}
      title="Link your projects"
      description="Pick up to three repositories. We'll analyse them in the background while you finish the rest — you won't wait on it."
    >
      {needsConnect ? (
        <p className="rounded-xl border border-[var(--flagged)]/30 bg-[var(--flagged)]/10 p-4 text-sm text-[var(--slate)]">
          Connect GitHub on the previous stage first — that&apos;s where this list comes from.
        </p>
      ) : repos.isPending || projects.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
        </div>
      ) : repos.isError ? (
        <p role="alert" className="text-sm text-rejected">
          {getProfileErrorMessage(repos.error, "Could not load your repositories.")}
        </p>
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-[var(--slate)]">
            {selected.length} of {MAX_REPOS} selected.
            {selected.length >= MAX_REPOS
              ? " Up to 3 for now — you can add more after verification."
              : ""}
          </p>

          <ul className="max-h-[26rem] space-y-2 overflow-y-auto pr-1">
            {repos.data?.map((repo) => {
              const checked = selected.includes(repo.full_name);
              const disabled = !checked && selected.length >= MAX_REPOS;

              return (
                <li key={repo.full_name}>
                  <label
                    title={disabled ? "Up to 3 projects for now — you can add more after verification." : undefined}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition",
                      checked ? "border-[var(--rule)] bg-[var(--panel)]" : "border-[var(--rule)] bg-[var(--panel)]",
                      disabled && "cursor-not-allowed opacity-50",
                    )}
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
                        {repo.fork ? (
                          <GitFork size={12} className="shrink-0 text-[var(--muted)]" aria-hidden="true" />
                        ) : null}
                      </p>
                      <p className="mt-1 flex flex-wrap items-center gap-3 text-xs text-[var(--muted)]">
                        {repo.language ? <span>{repo.language}</span> : null}
                        <span className="flex items-center gap-1">
                          <Star size={11} aria-hidden="true" /> {repo.stargazers_count}
                        </span>
                        {repo.updated_at ? (
                          <span>Updated {new Date(repo.updated_at).toLocaleDateString()}</span>
                        ) : null}
                      </p>
                    </div>
                  </label>

                  {checked ? (
                    <div className="ml-8 mt-2 flex flex-col gap-1">
                      <label
                        htmlFor={`note-${repo.full_name}`}
                        className="text-xs font-medium text-[var(--slate)]"
                      >
                        Your role / contribution (optional)
                      </label>
                      <textarea
                        id={`note-${repo.full_name}`}
                        rows={2}
                        maxLength={MAX_CONTRIBUTION_CHARS}
                        value={notes[repo.full_name] ?? ""}
                        onChange={(event) =>
                          setNotes((current) => ({ ...current, [repo.full_name]: event.target.value }))
                        }
                        placeholder="What did you build, or what was your specific contribution?"
                        className="w-full rounded border border-[var(--rule)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] outline-none transition focus:border-[var(--rule)] "
                      />
                      <span className="self-end text-[11px] text-[var(--muted)]">
                        {(notes[repo.full_name] ?? "").length}/{MAX_CONTRIBUTION_CHARS}
                      </span>
                    </div>
                  ) : null}
                </li>
              );
            })}

            {repos.data?.length === 0 ? (
              <p className="py-6 text-center text-sm text-[var(--slate)]">
                No repositories found on your account.
              </p>
            ) : null}
          </ul>

          {error ? (
            <p role="alert" className="text-xs text-rejected">
              {error}
            </p>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--rule)] pt-4">
            <Button type="button" variant="secondary" onClick={goBack} disabled={busy}>
              Previous
            </Button>
            <Button
              type="button"
              onClick={() => void onContinue()}
              isLoading={busy}
              // The minimum is the gate: one project is what makes the
              // pipeline able to run at all.
              disabled={selected.length === 0 || busy}
            >
              {busy ? "Linking…" : "Continue"}
            </Button>
          </div>
        </div>
      )}
    </StageShell>
  );
}

/** `owner/name` from a GitHub URL, or null for a project that has no repo (a
 * described project, or a URL from somewhere else). Used to line up the
 * server's project rows with the picker's repository list. */
function repoFullName(repoUrl: string | null): string | null {
  if (!repoUrl) return null;
  try {
    const parsed = new URL(repoUrl);
    if (parsed.hostname.replace(/^www\./, "") !== "github.com") return null;
    const parts = parsed.pathname.split("/").filter(Boolean);
    return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : null;
  } catch {
    return null;
  }
}
