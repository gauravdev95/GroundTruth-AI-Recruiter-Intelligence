import { AlertTriangle, Check, CircleDashed, Loader2, Minus, X } from "lucide-react";
import { useEffect, useState } from "react";

import { DURATION, EASE, STAGGER, subscribeFrame, useReducedMotionSafe } from "@/design/motion";
import { Reveal } from "@/design/primitives";

import type { ActivityStage, ActivityStageState } from "../api/activityApi";
import { useActivityFeed } from "../hooks/useActivityFeed";

/**
 * The analysis feed — a build log, not a spinner.
 *
 * WHY THIS SCREEN LOOKS LIKE CI OUTPUT
 *
 * The student has just handed over their resume, their GitHub account and a
 * list of claims, and the platform is about to spend a minute checking all of
 * it against third parties. That minute is the most anxious point in the whole
 * onboarding, and it is also the moment the product's core promise is being
 * kept for the first time. A spinner wastes it. A log spends it proving that
 * something specific and real is happening to each individual claim.
 *
 * WHAT THIS COMPONENT REFUSES TO DO
 *
 * * **No percentage.** No stage can report one — see `activityApi.ts`.
 * * **No fake advancement.** Every row's state comes from the server. Nothing
 *   here advances on a timer, and there is no minimum display duration that
 *   would hold a finished stage on screen to look more impressive.
 * * **No hidden failures.** A failed stage is rendered as failed, with its
 *   reason, immediately. A loading screen that quietly swallows an error and
 *   spins forever is the worst outcome available on this screen.
 *
 * The one thing that IS animated without server input is the elapsed timer on
 * a running row, because time genuinely is passing and the student's real
 * question at that moment is "is this stuck".
 */

const STATE_STYLES: Record<
  ActivityStageState,
  { icon: typeof Check; tint: string; ring: string }
> = {
  // Violet, not green: "this is running" is a UI state, and the colour rule
  // reserves green for proven claims.
  running: { icon: Loader2, tint: "text-[var(--violet)]", ring: "bg-[var(--violet)]/12" },
  succeeded: { icon: Check, tint: "text-[var(--verified)]", ring: "bg-[var(--verified)]/12" },
  inconclusive: { icon: AlertTriangle, tint: "text-[var(--flagged)]", ring: "bg-[var(--flagged)]/12" },
  failed: { icon: X, tint: "text-[var(--failed)]", ring: "bg-[var(--failed)]/12" },
  pending: { icon: CircleDashed, tint: "text-[var(--muted)]", ring: "bg-[var(--rule)]/40" },
  skipped: { icon: Minus, tint: "text-[var(--muted)]", ring: "bg-[var(--rule)]/40" },
};

/**
 * The sentence under each row's title.
 *
 * Built from the raw `total`/`settled` counts rather than sent pre-rendered
 * from the server, so tense and pluralisation stay a client concern — the
 * backend returns facts, the UI writes English.
 */
function describe(stage: ActivityStage): string {
  const { state, total, settled, detail } = stage;
  const noun = total === 1 ? "claim" : "claims";

  switch (state) {
    case "pending":
      return total > 0 ? `${total} ${noun} queued` : "Waiting to start";
    case "running":
      return `Checking ${settled + 1} of ${total}`;
    case "succeeded":
      return total === 1 ? "Confirmed" : `${settled} of ${total} checked`;
    case "inconclusive":
      // Deliberately explicit that nothing was *disproved*. "Could not
      // confirm" is the honest phrasing; "failed" would tell a student their
      // claim was rejected when it merely went unconfirmed.
      return "Checked — we could not confirm this independently";
    case "failed":
      return detail ?? "We could not complete this check";
    case "skipped":
      return "Nothing to check";
  }
}

/** Live seconds since a running stage started. */
function Elapsed({ startedAt, asOf }: { startedAt: string; asOf: string }) {
  const reduced = useReducedMotionSafe();
  // Offset between the server's snapshot time and this device's clock, fixed
  // at mount. Rendering `Date.now() - startedAt` directly would show a wrong
  // (or negative) duration on any device whose clock is off.
  const [seconds, setSeconds] = useState(() =>
    Math.max(0, (Date.parse(asOf) - Date.parse(startedAt)) / 1000),
  );

  useEffect(() => {
    if (reduced) return;
    const base = Math.max(0, (Date.parse(asOf) - Date.parse(startedAt)) / 1000);
    const mountedAt = performance.now();
    return subscribeFrame((now) => {
      setSeconds(base + (now - mountedAt) / 1000);
    });
  }, [startedAt, asOf, reduced]);

  return (
    <span className="machine tabular text-[11px] text-[var(--muted)]">{seconds.toFixed(0)}s</span>
  );
}

function StageRow({ stage, asOf, index }: { stage: ActivityStage; asOf: string; index: number }) {
  const style = STATE_STYLES[stage.state];
  const Icon = style.icon;
  const isRunning = stage.state === "running";

  return (
    <Reveal delay={index * STAGGER.workerLine} trigger="mount" as="li">
      <div className="flex items-start gap-3 rounded-[var(--r-md)] px-3 py-2.5 transition-colors hover:bg-[var(--rule-soft)]">
        <span
          className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full ${style.ring}`}
        >
          <Icon
            size={13}
            className={`${style.tint} ${isRunning ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <p className="truncate text-sm font-medium text-[var(--ink)]">{stage.label}</p>
            {isRunning && stage.started_at ? (
              <Elapsed startedAt={stage.started_at} asOf={asOf} />
            ) : null}
          </div>
          <p className="mt-0.5 text-xs text-[var(--slate)]">{describe(stage)}</p>
        </div>
      </div>
    </Reveal>
  );
}

export function AnalysisFeed({ enabled = true }: { enabled?: boolean }) {
  const feed = useActivityFeed({ enabled });

  if (feed.isPending) {
    return (
      <ul className="space-y-1" aria-busy="true">
        {Array.from({ length: 5 }).map((_, index) => (
          <li key={index} className="flex items-center gap-3 px-3 py-2.5">
            <span className="h-6 w-6 shrink-0 animate-pulse rounded-full bg-[var(--rule)]" />
            <span className="h-3 w-40 animate-pulse rounded bg-[var(--rule)]" />
          </li>
        ))}
      </ul>
    );
  }

  if (feed.isError || !feed.data) {
    // The work is still running on the server regardless of whether this poll
    // succeeded, so the copy must not imply the analysis itself broke.
    return (
      <p className="rounded-[var(--r-md)] border border-[var(--rule)] px-4 py-3 text-sm text-[var(--slate)]">
        We could not load the live status. Your profile is still being analysed — refresh in a
        moment.
      </p>
    );
  }

  const { stages, as_of, is_running } = feed.data;
  const settled = stages.filter(
    (stage) => stage.state !== "pending" && stage.state !== "running",
  ).length;

  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between px-3">
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
          {is_running ? "Analysing your profile" : "Analysis complete"}
        </p>
        <p className="machine tabular text-[11px] text-[var(--muted)]">
          {settled}/{stages.length}
        </p>
      </div>

      <ul className="space-y-0.5">
        {stages.map((stage, index) => (
          <StageRow key={stage.key} stage={stage} asOf={as_of} index={index} />
        ))}
      </ul>

      {/*
        A single hairline that fills as stages settle. This IS derived from
        real completion — settled stages over total stages — so it is not the
        invented progress the module docstring rules out. It is deliberately
        1px and unlabelled: a number here would imply a precision the stage
        count does not have, since stages take wildly different durations.
      */}
      <div className="mx-3 mt-4 h-px overflow-hidden rounded-full bg-[var(--rule)]">
        <ProgressHairline value={settled / Math.max(1, stages.length)} />
      </div>
    </div>
  );
}

function ProgressHairline({ value }: { value: number }) {
  const reduced = useReducedMotionSafe();
  return (
    <div
      className="h-full origin-left"
      style={{
        width: "100%",
        transform: `scaleX(${value})`,
        background: "linear-gradient(90deg, var(--violet), var(--blue))",
        transition: reduced
          ? "none"
          : `transform ${DURATION.slow}s cubic-bezier(${EASE.entrance.join(",")})`,
      }}
    />
  );
}
