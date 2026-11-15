import { Loader2 } from "lucide-react";

import { Card, EmptyState } from "@/components";
import { cn } from "@/lib/utils";

import type { ActivityStage, ActivityStageState } from "../onboarding/api/activityApi";
import { useActivityFeed } from "../onboarding/hooks/useActivityFeed";

/**
 * The verification pipeline, as a timeline of what the workers have actually
 * done to this profile. Every row comes from `GET /student/profile/onboarding/activity`
 * — no timers, no invented percentages (the backend deliberately reports none).
 *
 * State colours are status colours, because these *are* statuses: a stage
 * that finished is `--verified`, one whose evidence did not hold is
 * `--flagged` (inconclusive is not a failure), one that errored is
 * `--failed`, and one still running is `--blue` — a measurement in progress,
 * not a claim.
 */
const STATE_STYLE: Record<ActivityStageState, { dot: string; label: string }> = {
  succeeded: { dot: "bg-[var(--verified)]", label: "Done" },
  running: { dot: "bg-[var(--blue)]", label: "Running" },
  pending: { dot: "bg-[var(--muted)]", label: "Waiting" },
  inconclusive: { dot: "bg-[var(--flagged)]", label: "Inconclusive" },
  failed: { dot: "bg-[var(--failed)]", label: "Failed" },
  skipped: { dot: "bg-[var(--muted)]", label: "Skipped" },
};

function formatTime(iso: string | null): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function StageRow({ stage, isLast }: { stage: ActivityStage; isLast: boolean }) {
  const style = STATE_STYLE[stage.state];
  const time = formatTime(stage.finished_at ?? stage.started_at);

  return (
    <li className="relative flex gap-3 pb-5 last:pb-0">
      {!isLast ? (
        <span aria-hidden="true" className="absolute left-[5px] top-4 h-[calc(100%-1rem)] w-px bg-[var(--rule)]" />
      ) : null}
      <span
        aria-hidden="true"
        className={cn(
          "relative mt-1.5 size-2.5 shrink-0 rounded-full",
          style.dot,
          stage.state === "running" && "animate-pulse",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm font-medium text-[var(--ink)]">{stage.label}</p>
          <span className="shrink-0 text-xs text-[var(--muted)]">{style.label}</span>
        </div>
        <p className="mt-0.5 text-xs text-[var(--slate)]">
          {stage.total > 0 ? (
            <>
              {stage.settled} of {stage.total} checked
              {time ? ` · ${time}` : ""}
            </>
          ) : (
            (time ?? "Not started yet")
          )}
        </p>
        {stage.detail ? <p className="mt-0.5 text-xs text-[var(--failed)]">{stage.detail}</p> : null}
      </div>
    </li>
  );
}

export function ActivityTimeline() {
  const feed = useActivityFeed();

  if (feed.isPending) {
    return (
      <Card title="Verification activity" subtitle="What our checks have done so far.">
        <div className="flex items-center gap-2 text-sm text-[var(--slate)]">
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          Loading activity…
        </div>
      </Card>
    );
  }

  if (feed.isError || !feed.data) return null;

  const stages = feed.data.stages;
  if (stages.length === 0) {
    return (
      <Card title="Verification activity" subtitle="What our checks have done so far.">
        <EmptyState
          title="No verification activity yet"
          description="Checks start once your profile is submitted. They run in the background and you'll be emailed when they finish."
        />
      </Card>
    );
  }

  return (
    <Card
      title="Verification activity"
      subtitle={
        feed.data.is_running
          ? "Checks are running in the background — this list updates as they finish."
          : "The latest status of each check on your profile."
      }
    >
      <ol>
        {stages.map((stage, index) => (
          <StageRow key={stage.key} stage={stage} isLast={index === stages.length - 1} />
        ))}
      </ol>
    </Card>
  );
}
