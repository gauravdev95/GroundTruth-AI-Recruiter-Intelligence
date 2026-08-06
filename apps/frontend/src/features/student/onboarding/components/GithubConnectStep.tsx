import { useMutation } from "@tanstack/react-query";
import { AlertCircle, Check, GitBranch, Github, ScanSearch, Star, Users } from "lucide-react";

import { STAGGER } from "@/design/motion";
import { Celebrate, Reveal, Stagger } from "@/design/primitives";
import { Surface } from "@/design/Surface";
import { githubApi } from "@/features/student/api/githubApi";

/**
 * GitHub connection — deliberately the FIRST step of onboarding.
 *
 * WHY THIS MOVED TO THE FRONT
 *
 * It used to sit inside the Technical section, several steps in. Moving it
 * first is the highest-leverage change in the whole flow, because GitHub is
 * the only input that makes the *rest* of onboarding shorter rather than
 * longer:
 *
 * * Repositories become selectable projects, so the Projects section is a
 *   picker instead of a form.
 * * Detected technologies pre-fill skills with real evidence weight behind
 *   them, rather than as self-declared claims worth nothing to matching.
 * * `verify_repository_task` needs the OAuth token to read private repo
 *   metadata and to raise the API rate limit; connecting late means the
 *   analysis queue starts late, and the interview is gated on it.
 *
 * Put simply: connecting first means the background workers start while the
 * student is still filling in the rest, instead of after. On the old
 * ordering the student finished the form and *then* waited.
 *
 * SKIPPING IS ALLOWED, AND THE COST IS STATED PLAINLY
 *
 * A student with no public code is a real user, not an edge case, and a hard
 * gate here would end their signup. But an unexplained "Skip" teaches them
 * nothing, so the skip path names exactly what stays locked. That honesty is
 * also self-interested: a student who understands what they lost is far more
 * likely to come back and connect later.
 */

const BENEFITS = [
  {
    icon: ScanSearch,
    title: "Repository analysis",
    body: "Fork detection, your real contribution share, and the technologies actually present in each project.",
  },
  {
    icon: GitBranch,
    title: "Projects without typing",
    body: "Pick repositories from a list instead of writing them out by hand.",
  },
  {
    icon: Star,
    title: "Skills backed by evidence",
    body: "Technologies detected from your dependency manifests carry weight in matching. Self-declared ones do not.",
  },
  {
    icon: Users,
    title: "A code-grounded interview",
    body: "Your AI interview asks about the code you actually wrote — which is what recruiters weigh most.",
  },
];

interface GithubConnectStepProps {
  /** Set once the OAuth round trip has completed. */
  connected?: {
    username: string;
    avatarUrl?: string | null;
    publicRepos?: number | null;
    followers?: number | null;
  } | null;
  onSkip: () => void;
  onContinue: () => void;
}

export function GithubConnectStep({ connected, onSkip, onContinue }: GithubConnectStepProps) {
  const connect = useMutation({
    mutationFn: githubApi.connect,
    onSuccess: ({ authorize_url }) => {
      // Full-page navigation, not XHR: this is an OAuth authorize URL and the
      // browser must own the redirect for the callback cookie to land.
      window.location.href = authorize_url;
    },
  });

  if (connected) {
    return (
      <div className="mx-auto max-w-[560px] px-6 py-14 text-center">
        <Celebrate active className="inline-block">
          <span className="grid h-16 w-16 place-items-center rounded-full bg-[var(--verified)]/12">
            <Check size={26} className="text-[var(--verified)]" aria-hidden="true" />
          </span>
        </Celebrate>

        <Reveal trigger="mount" delay={STAGGER.siblings}>
          <h2 className="mt-6 font-[family-name:var(--disp)] text-2xl font-semibold text-[var(--ink)]">
            GitHub connected
          </h2>
          <p className="mt-2 text-sm text-[var(--slate)]">
            We can start analysing your repositories while you finish the rest.
          </p>
        </Reveal>

        <Reveal trigger="mount" delay={STAGGER.siblings * 2}>
          <Surface elevation="raised" className="mt-7 flex items-center gap-4 p-4 text-left">
            {connected.avatarUrl ? (
              <img
                src={connected.avatarUrl}
                alt=""
                className="h-11 w-11 rounded-full border border-[var(--rule)]"
              />
            ) : (
              <span className="grid h-11 w-11 place-items-center rounded-full bg-[var(--rule)]">
                <Github size={18} className="text-[var(--slate)]" aria-hidden="true" />
              </span>
            )}
            <div className="min-w-0 flex-1">
              <p className="machine truncate text-sm font-medium text-[var(--ink)]">
                {connected.username}
              </p>
              <p className="mt-0.5 text-xs text-[var(--slate)]">
                {/*
                  Only rendered when the API actually returned a count.
                  "0 repositories" and "we did not receive a count" are
                  different facts, and printing the former for the latter
                  would be a small lie on a screen about verification.
                */}
                {connected.publicRepos != null
                  ? `${connected.publicRepos} public ${
                      connected.publicRepos === 1 ? "repository" : "repositories"
                    }`
                  : "Connected"}
                {connected.followers != null ? ` · ${connected.followers} followers` : ""}
              </p>
            </div>
          </Surface>
        </Reveal>

        <Reveal trigger="mount" delay={STAGGER.siblings * 3}>
          <button
            type="button"
            onClick={onContinue}
            className="mt-8 w-full rounded-[var(--r-full)] px-6 py-3 text-sm font-semibold text-white"
            style={{ backgroundImage: "linear-gradient(100deg, var(--violet), var(--blue))" }}
          >
            Continue
          </button>
        </Reveal>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[560px] px-6 py-14">
      <Reveal trigger="mount">
        <div className="text-center">
          <span className="inline-grid h-14 w-14 place-items-center rounded-[var(--r-lg)] bg-[var(--ink)]/5 ring-1 ring-[var(--rule)]">
            <Github size={26} className="text-[var(--ink)]" aria-hidden="true" />
          </span>
          <h2 className="mt-5 font-[family-name:var(--disp)] text-2xl font-semibold text-[var(--ink)]">
            Connect GitHub
          </h2>
          <p className="mx-auto mt-2 max-w-[42ch] text-sm leading-relaxed text-[var(--slate)]">
            This is what turns a list of claims into a profile with proof behind it. It is also
            the fastest way through the rest of setup.
          </p>
        </div>
      </Reveal>

      <Stagger className="mt-8 space-y-2.5" interval={STAGGER.siblings}>
        {BENEFITS.map(({ icon: Icon, title, body }) => (
          <Stagger.Item key={title}>
            <Surface className="flex items-start gap-3.5 p-3.5">
              <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-[var(--r-sm)] bg-[var(--verified)]/12">
                <Icon size={13} className="text-[var(--verified)]" aria-hidden="true" />
              </span>
              <div>
                <p className="text-[13px] font-medium text-[var(--ink)]">{title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-[var(--slate)]">{body}</p>
              </div>
            </Surface>
          </Stagger.Item>
        ))}
      </Stagger>

      {connect.isError ? (
        <Surface className="mt-5 flex items-start gap-3 border-[var(--failed)]/30 p-3.5">
          <AlertCircle size={15} className="mt-0.5 shrink-0 text-[var(--failed)]" aria-hidden="true" />
          <div className="text-[13px]">
            <p className="font-medium text-[var(--ink)]">We could not reach GitHub</p>
            {/* Every error state offers the next action, never just the news. */}
            <p className="mt-0.5 text-[var(--slate)]">
              Try again in a moment, or skip this step and connect later from your profile.
            </p>
          </div>
        </Surface>
      ) : null}

      <Reveal trigger="mount" delay={STAGGER.siblings * 5}>
        <div className="mt-8 space-y-3">
          <button
            type="button"
            onClick={() => connect.mutate()}
            disabled={connect.isPending}
            className="flex w-full items-center justify-center gap-2.5 rounded-[var(--r-full)] bg-[var(--ink)] px-6 py-3.5 text-sm font-semibold text-[var(--bg)] transition-colors hover:bg-[var(--ink-hover)] disabled:opacity-60"
          >
            <Github size={16} aria-hidden="true" />
            {connect.isPending ? "Opening GitHub…" : "Connect GitHub"}
          </button>

          <button
            type="button"
            onClick={onSkip}
            className="w-full rounded-[var(--r-full)] px-6 py-2.5 text-[13px] text-[var(--slate)] transition-colors hover:text-[var(--ink)]"
          >
            Skip for now
          </button>

          {/*
            The cost of skipping, stated before the click rather than
            discovered afterwards. Amber, because this is the "claimed but
            unchecked" state the rest of the product uses that colour for.
          */}
          <p className="text-center text-[11px] leading-relaxed text-[var(--muted)]">
            Without GitHub your projects stay{" "}
            <span className="text-[var(--flagged)]">unverified</span>, your skills carry no
            evidence weight in matching, and your interview cannot be grounded in real code. You
            can connect any time from your profile.
          </p>
        </div>
      </Reveal>
    </div>
  );
}
