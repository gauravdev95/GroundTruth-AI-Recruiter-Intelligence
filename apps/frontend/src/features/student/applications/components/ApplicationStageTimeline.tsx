import { Check, X } from "lucide-react";

import { cn } from "@/lib/utils";

import type { Application } from "../api/applicationsApi";
import { buildStageTimeline, type TimelineStage } from "../lib/stageTimeline";

function StageDot({ stage }: { stage: TimelineStage }) {
  if (stage.state === "done") {
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--violet)] text-white">
        <Check size={12} aria-hidden="true" />
      </span>
    );
  }
  if (stage.id === "rejected") {
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--failed)]/12 text-[var(--failed)]">
        <X size={12} aria-hidden="true" />
      </span>
    );
  }
  if (stage.state === "current") {
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-[var(--violet)] bg-[var(--panel)]">
        <span className="h-2 w-2 rounded-full bg-[var(--violet)]" />
      </span>
    );
  }
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-[var(--rule)] bg-[var(--panel)]" />
  );
}

/**
 * Where this application stands, as a vertical timeline.
 *
 * The stages are the backend's own linear path (`ALLOWED_TRANSITIONS` in
 * `pipeline/models.py`), so a current stage implies the earlier ones — the
 * only inference made, and it is the backend's rule. A date is shown only
 * where the API supplies one: `applied_at` for Applied,
 * `status_updated_at` for the current stage. Intermediate stages carry no
 * date because none is recorded.
 *
 * A rejection ends the timeline with a terminal "Not selected" step and no
 * invented middle stages: the API does not record which stage the
 * application was rejected from, so neither "reached" nor "not reached"
 * is claimed for them.
 */
export function ApplicationStageTimeline({ application }: { application: Application }) {
  const stages = buildStageTimeline(
    application.status,
    application.applied_at,
    application.status_updated_at,
  );
  const isRejected = application.status === "rejected";

  return (
    <div>
      <ol className="space-y-0">
        {stages.map((stage, index) => (
          <li key={stage.id} className="relative flex gap-3 pb-5 last:pb-0">
            {index < stages.length - 1 ? (
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-3 top-6 h-[calc(100%-1.25rem)] w-px",
                  stage.state === "done" ? "bg-[var(--violet)]/50" : "bg-[var(--rule)]",
                )}
              />
            ) : null}
            <StageDot stage={stage} />
            <div className="min-w-0 pt-0.5">
              <p
                className={cn(
                  "text-sm font-medium",
                  stage.state === "upcoming" ? "text-[var(--muted)]" : "text-[var(--ink)]",
                )}
              >
                {stage.label}
                {stage.state === "current" && stage.id !== "rejected" ? (
                  <span className="ml-2 rounded-full bg-[var(--violet)]/12 px-2 py-0.5 text-[11px] font-medium text-[var(--violet)]">
                    Current stage
                  </span>
                ) : null}
              </p>
              {stage.date ? (
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  {stage.dateLabel} {stage.date}
                </p>
              ) : stage.state === "upcoming" ? (
                <p className="mt-0.5 text-xs text-[var(--muted)]">Not reached yet</p>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      {isRejected ? (
        <p className="mt-4 border-t border-[var(--rule-soft)] pt-3 text-xs leading-relaxed text-[var(--muted)]">
          Only the current stage is recorded, so the stages before this decision aren&rsquo;t
          shown here. A recruiter moved this application — nothing here was decided
          automatically.
        </p>
      ) : null}
    </div>
  );
}
