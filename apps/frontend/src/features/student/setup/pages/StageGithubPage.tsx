import { useMutation } from "@tanstack/react-query";
import { AlertCircle, Check, ExternalLink, Github, Loader2 } from "lucide-react";

import { Button, Skeleton } from "@/components";

import { githubApi } from "../../api/githubApi";
import { VerificationBadge } from "../../components/SectionBadges";
import { useTechnicalSection } from "../../hooks/useProfileSection";
import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { StageShell } from "../components/StageShell";
import { useStageNav } from "../hooks/useStageNav";
import { stageByStepKey } from "../lib/stages";

const STAGE = stageByStepKey("github")!;

/**
 * What we read, why, and for how long — shown *before* the redirect, not
 * after. DPDP requires informed consent, and consent given after the
 * permission grant is not informed. The final consent to *act* on this data is
 * the review stage's checkbox; this is the disclosure that makes it meaningful.
 */
const DISCLOSURE = [
  "Repository names, commit history, and the contents of your public repositories.",
  "Used to verify authorship of the projects you link and to generate interview questions from your own code.",
  "Read-only. No write permissions, and no access to private repositories unless you grant it separately.",
  "Kept while your profile is active. Disconnecting removes our access and stops further reads.",
];

/**
 * Stage 2 — connect GitHub. Mandatory.
 *
 * **There is no "Skip for now" here, unlike every other version of this
 * screen.** GitHub is what the evidence pipeline runs on: without it, projects
 * cannot be verified, skills carry no evidence weight, and the interview
 * cannot be grounded in real code. A profile that skipped it reaches the
 * dashboard and can never become discoverable through the repository path, so
 * accepting one was accepting a profile the platform cannot act on.
 *
 * The spec's alternative for a student with no GitHub — uploading a .zip — is
 * not built. It is deliberately not stubbed either: every stage of the
 * pipeline (fork detection, contribution share, commit-history analysis) reads
 * the GitHub API, and an archive has no commit history, so "treated the same
 * as a linked repo" is not achievable without redesigning verification. A
 * student in that position needs to hear that, not a button that half-works.
 */
export function StageGithubPage() {
  const { advance, goBack } = useStageNav();
  const technical = useTechnicalSection();
  const account = technical.data?.data.github_account ?? null;

  const connect = useMutation({
    mutationFn: githubApi.connect,
    onSuccess: ({ authorize_url }) => {
      // Full-page navigation, not XHR: this is an OAuth authorize URL and the
      // browser has to own the redirect for the callback to land.
      window.location.href = authorize_url;
    },
  });

  return (
    <StageShell
      stage={STAGE}
      title="Connect your GitHub"
      description="We read your public repositories to verify your work. Read-only access, no write permissions, and you can disconnect any time."
    >
      {technical.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-11 w-48 rounded-full" />
        </div>
      ) : account ? (
        <div className="space-y-5">
          {/* The connected account, visualised from the API row itself —
              username, profile URL and verification outcome are all server
              data; nothing here is typed in or assumed. The username is mono:
              it is machine-read from GitHub, not something the student wrote. */}
          <div className="rounded-[var(--r-lg)] border border-[var(--verified)]/30 bg-[var(--verified)]/10 p-5">
            <div className="flex items-start gap-4">
              <span
                aria-hidden="true"
                className="flex size-12 shrink-0 items-center justify-center rounded-full bg-[var(--panel-raised)] text-[var(--ink)]"
              >
                <Github size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="machine truncate text-base font-semibold text-[var(--ink)]">
                    {account.github_username}
                  </p>
                  <VerificationBadge status={account.verification_status} />
                </div>
                <a
                  href={account.profile_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-flex items-center gap-1 truncate text-xs text-[var(--slate)] underline-offset-4 hover:text-[var(--ink)] hover:underline"
                >
                  <span className="machine truncate">{account.profile_url}</span>
                  <ExternalLink size={11} className="shrink-0" aria-hidden="true" />
                </a>
                <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--slate)]">
                  <div className="flex gap-1.5">
                    <dt className="text-[var(--muted)]">Verified</dt>
                    <dd className="font-medium text-[var(--ink)]">
                      {account.verified_at
                        ? new Date(account.verified_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })
                        : "Not yet verified"}
                    </dd>
                  </div>
                  {account.verification_score !== null && account.verification_score !== undefined ? (
                    <div className="flex gap-1.5">
                      <dt className="text-[var(--muted)]">Verification score</dt>
                      <dd className="font-mono tabular-nums text-[var(--ink)]">
                        {/* 0-100 per `models.py` — the check's own confidence,
                            not a fraction. */}
                        {Math.round(account.verification_score)}/100
                      </dd>
                    </div>
                  ) : null}
                </dl>
              </div>
              <span
                aria-hidden="true"
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[var(--verified)]/15"
              >
                <Check size={16} className="text-[var(--verified)]" />
              </span>
            </div>
            <p className="mt-4 border-t border-[var(--verified)]/20 pt-3 text-xs leading-relaxed text-[var(--slate)]">
              Connected. We&apos;ll start analysing your repositories once you link them on the
              next stage.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--rule)] pt-4">
            <Button type="button" variant="secondary" onClick={goBack}>
              Previous
            </Button>
            <Button type="button" onClick={advance}>
              Continue
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-4">
            <h2 className="text-sm font-semibold text-[var(--ink)]">Before you connect</h2>
            <ul className="mt-2.5 space-y-1.5">
              {DISCLOSURE.map((line) => (
                <li key={line} className="flex gap-2 text-xs leading-relaxed text-[var(--slate)]">
                  <span aria-hidden="true" className="mt-1.5 size-1 shrink-0 rounded-full bg-[var(--muted)]" />
                  {line}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-[var(--slate)]">
              Full detail in our{" "}
              <a href="/legal/privacy" className="underline hover:text-[var(--ink)]">
                privacy policy
              </a>
              .
            </p>
          </div>

          {connect.isError ? (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl border border-[var(--failed)]/30 bg-[var(--failed)]/10 p-3.5"
            >
              <AlertCircle size={15} className="mt-0.5 shrink-0 text-[var(--failed)]" aria-hidden="true" />
              <div className="text-xs">
                <p className="font-medium text-[var(--ink)]">We could not reach GitHub</p>
                <p className="mt-0.5 text-[var(--slate)]">
                  {getProfileErrorMessage(connect.error, "Try again in a moment.")}
                </p>
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--rule)] pt-4">
            <Button type="button" variant="secondary" onClick={goBack}>
              Previous
            </Button>
            <Button type="button" onClick={() => connect.mutate()} disabled={connect.isPending}>
              {connect.isPending ? (
                <Loader2 size={15} className="mr-1.5 animate-spin" aria-hidden="true" />
              ) : (
                <Github size={15} className="mr-1.5" aria-hidden="true" />
              )}
              {connect.isPending ? "Opening GitHub…" : "Connect with GitHub"}
            </Button>
          </div>

          {/* Says plainly that the alternative does not exist yet, rather than
              offering a path that would produce weaker evidence while looking
              identical to the real one. */}
          <p className="text-center text-xs leading-relaxed text-[var(--muted)]">
            No GitHub account? Everything we verify is read from commit history, so there
            isn&apos;t a way to prove authorship without it yet. Create a free account and push
            your code, then come back — your progress is saved.
          </p>
        </div>
      )}
    </StageShell>
  );
}
