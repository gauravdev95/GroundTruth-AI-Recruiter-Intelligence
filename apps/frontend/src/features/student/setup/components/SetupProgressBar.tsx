import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

import type { SetupStep } from "../api/setupApi";
import { ONBOARDING_STAGES, type OnboardingStage } from "../lib/stages";

interface SetupProgressBarProps {
  stage: OnboardingStage;
  /** Server step state, keyed by `SetupStep.key`. Used only for the check
   * marks — which stages have content — never for the percentage. */
  steps: SetupStep[] | undefined;
  onSelect?: (stage: OnboardingStage) => void;
}

/**
 * The persistent header across every `/student/profile/setup/*` route.
 *
 * **The percentage is flow position, and it says so.** `stage.percent` is a
 * constant per stage (15, 30, 50, …) — where you are in the sequence, which is
 * a fact the client knows outright. It is deliberately *not*
 * `completion_percentage`, which is the server's weighted profile strength and
 * a different measurement: a student who skips all three optional stages
 * finishes this flow completely while scoring 60 there, and showing that
 * number under a wizard header would tell them they had failed at the moment
 * they succeeded.
 *
 * The label is explicit about which one it is ("Step 4 of 8 · 50% through
 * setup"), because an unlabelled percentage in a product that also has a
 * profile-strength score is two numbers the student has no way to tell apart.
 * Profile strength keeps its own meter on the review stage.
 *
 * Check marks come from the server's `SetupStep.status` rather than from
 * position, so a stage the student filled and then navigated back past still
 * reads as done — position alone would un-tick it.
 */
export function SetupProgressBar({ stage, steps, onSelect }: SetupProgressBarProps) {
  const index = ONBOARDING_STAGES.indexOf(stage);
  const statusByKey = new Map((steps ?? []).map((step) => [step.key, step.status]));

  return (
    <section
      aria-label="Onboarding progress"
      className="rounded-2xl border border-[var(--violet)]/25 bg-[var(--panel)] p-5 shadow-sm shadow-[var(--shadow-panel)] sm:p-6"
    >
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-sm font-semibold text-[var(--ink)]">
          Step {index + 1} of {ONBOARDING_STAGES.length} · {stage.label}
        </h2>
        <span className="shrink-0 rounded-full bg-[var(--violet)]/10 px-3 py-1 text-xs font-semibold text-[var(--violet)]">
          {stage.percent}% through setup
        </span>
      </div>

      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--violet)]/15"
        role="progressbar"
        aria-valuenow={stage.percent}
        aria-valuemin={0}
        aria-valuemax={100}
        // Named, not just "progress": this page can show two percentages and
        // a screen reader has no colour or position to tell them apart.
        aria-label="Progress through onboarding"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-[var(--violet)] to-[var(--blue)] transition-[width] duration-500"
          style={{ width: `${stage.percent}%` }}
        />
      </div>

      {/* The dot rail is supplementary — the line above already carries the
          whole message — so it is hidden below `md` rather than reflowed. */}
      <ol className="mt-4 hidden md:flex md:items-center md:gap-1">
        {ONBOARDING_STAGES.map((item, itemIndex) => {
          const status = statusByKey.get(item.stepKey);
          const isFilled = status !== undefined && status !== "empty";
          const isActive = item === stage;
          const Wrapper = onSelect ? "button" : "div";

          return (
            <li key={item.stepKey} className="flex min-w-0 flex-1 items-center gap-1">
              <Wrapper
                {...(onSelect
                  ? {
                      type: "button" as const,
                      onClick: () => onSelect(item),
                      "aria-label": `Step ${itemIndex + 1}: ${item.label}`,
                    }
                  : {})}
                aria-current={isActive ? "step" : undefined}
                className={cn(
                  "flex min-w-0 flex-1 flex-col items-center gap-1.5 rounded-lg px-1 py-1",
                  onSelect &&
                    "transition hover:bg-[var(--violet)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--violet)]",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "flex size-7 shrink-0 items-center justify-center rounded-full border-2 text-[11px] font-semibold transition",
                    isActive
                      ? "border-[var(--violet)] bg-gradient-to-br from-[var(--violet)] to-[var(--blue)] text-white shadow-sm shadow-[var(--shadow-panel)]"
                      : isFilled
                        ? "border-[var(--violet)]/30 bg-[var(--violet)]/10 text-[var(--violet)]"
                        : "border-[var(--rule)] bg-[var(--panel)] text-[var(--muted)]",
                  )}
                >
                  {isFilled && !isActive ? <Check size={13} strokeWidth={3} /> : itemIndex + 1}
                </span>
                <span
                  className={cn(
                    "block truncate text-[11px] font-medium leading-tight",
                    isActive ? "text-[var(--ink)]" : isFilled ? "text-[var(--slate)]" : "text-[var(--muted)]",
                  )}
                >
                  {item.label}
                </span>
                {/* "Saved" and "verified" stay distinct for screen readers
                    here exactly as they do in the stepper this replaced. */}
                <span className="sr-only">
                  {status === "verified"
                    ? "Verified"
                    : status === "pending_verification"
                      ? "Saved, verification in progress"
                      : status === "saved"
                        ? "Saved"
                        : "Not started"}
                  {item.isMandatory ? "" : ", optional"}
                  {isActive ? ", current step" : ""}
                </span>
              </Wrapper>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/**
 * There is deliberately no skeleton variant of this component.
 *
 * Everything the bar renders unconditionally — the stage label, the step
 * count, the percentage — comes from the URL, which is known before any
 * request is made. Only the check marks need the server, and passing
 * `steps={undefined}` already draws those unticked. A skeleton would replace a
 * header that is entirely correct with a grey box, which is strictly less
 * information.
 */
