import { Check } from "lucide-react";

import { Skeleton } from "@/components";
import { cn } from "@/lib/utils";

import type { SetupStep } from "../api/setupApi";

interface SetupStepperProps {
  steps: SetupStep[];
  currentStepIndex: number;
  completionPercentage: number;
  /** Provided by the section builder; omitted on the entry screen, where there
   * is nothing to navigate to yet. Every step is passed regardless — a step is
   * never disabled, only unclickable when no handler exists. */
  onSelect?: (step: SetupStep) => void;
}

/**
 * The five-circle progress header.
 *
 * A separate component from `ProfileStepper` rather than a variant of it: that
 * one is a vertical sidebar list of buttons inside the builder, this is a
 * horizontal card that collapses to a "Step N of 5" strip on mobile. Sharing
 * one component would mean two layouts behind a flag and neither read clearly.
 *
 * Every number here is a server value. `completionPercentage` in particular is
 * `profile_strength` recomputed on the backend after each save — the client
 * never derives it from the step statuses, which would let a UI bug quietly
 * disagree with what recruiters actually filter on.
 */
export function SetupStepper({
  steps,
  currentStepIndex,
  completionPercentage,
  onSelect,
}: SetupStepperProps) {
  const current = steps[currentStepIndex];

  return (
    <section
      aria-label="Profile setup progress"
      className="rounded-2xl border border-violet-100 bg-white p-5 shadow-sm shadow-violet-900/5 sm:p-6"
    >
      <div className="mb-5 flex items-start justify-between gap-3">
        <h2 className="font-display text-sm font-semibold text-slate-900">Your progress</h2>
        <span className="shrink-0 rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">
          {completionPercentage}% Complete
        </span>
      </div>

      {/* Mobile: the five-across layout cannot survive a 360px viewport without
          truncating every label to uselessness, so it collapses to the one
          fact that matters — which step you are on and what it is called. */}
      <div className="md:hidden">
        <p className="text-xs font-semibold uppercase tracking-wide text-violet-600">
          Step {currentStepIndex + 1} of {steps.length}
        </p>
        <p className="mt-1 text-sm font-semibold text-slate-900">{current?.title}</p>
        <p className="mt-0.5 text-xs text-slate-500">{current?.subtitle}</p>
        <div
          className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-violet-100"
          role="progressbar"
          aria-valuenow={completionPercentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Profile completion"
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-600 transition-[width] duration-500"
            style={{ width: `${completionPercentage}%` }}
          />
        </div>
      </div>

      <ol className="hidden md:flex md:items-start">
        {steps.map((step, index) => {
          const isComplete = step.status !== "empty";
          const isActive = index === currentStepIndex;
          const Wrapper = onSelect ? "button" : "div";

          return (
            <li key={step.key} className="flex min-w-0 flex-1 items-start">
              <div className="flex min-w-0 flex-1 flex-col items-center px-1">
                <Wrapper
                  {...(onSelect
                    ? {
                        type: "button" as const,
                        onClick: () => onSelect(step),
                        "aria-label": `Step ${index + 1}: ${step.title}`,
                      }
                    : {})}
                  aria-current={isActive ? "step" : undefined}
                  className={cn(
                    "flex flex-col items-center rounded-xl px-2 py-1 text-center",
                    onSelect &&
                      "transition hover:bg-violet-50/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition",
                      isActive
                        ? "border-violet-600 bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-md shadow-violet-500/30"
                        : isComplete
                          ? "border-violet-200 bg-violet-50 text-violet-700"
                          : "border-slate-200 bg-white text-slate-400",
                    )}
                  >
                    {isComplete && !isActive ? <Check size={18} strokeWidth={3} /> : index + 1}
                  </span>

                  <span
                    className={cn(
                      "mt-2.5 block text-xs font-semibold leading-snug",
                      isActive ? "text-slate-900" : isComplete ? "text-slate-700" : "text-slate-400",
                    )}
                  >
                    {step.title}
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-slate-400">
                    {step.subtitle}
                  </span>

                  {/* Screen readers get the state the circle's colour encodes.
                      "Filled" and "verified" stay distinct here too. */}
                  <span className="sr-only">
                    {step.status === "verified"
                      ? "Verified"
                      : step.status === "pending_verification"
                        ? "Saved, verification in progress"
                        : step.status === "saved"
                          ? "Saved"
                          : "Not started"}
                    {isActive ? ", current step" : ""}
                  </span>
                </Wrapper>

                {isActive ? (
                  <span className="mt-2 rounded-full bg-violet-100 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                    Current Step
                  </span>
                ) : null}
              </div>

              {index < steps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "mt-5 h-0 flex-1 shrink-0 border-t-2 border-dotted",
                    isComplete ? "border-violet-300" : "border-slate-200",
                  )}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Shown while `setup-state` is in flight. The stepper never renders with
 * guessed values — a returning student would see their finished steps drawn as
 * empty for a beat, which reads as data loss. */
export function SetupStepperSkeleton() {
  return (
    <section
      aria-hidden="true"
      className="rounded-2xl border border-violet-100 bg-white p-5 shadow-sm shadow-violet-900/5 sm:p-6"
    >
      <div className="mb-5 flex items-center justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-6 w-28 rounded-full" />
      </div>
      <div className="flex items-start justify-between gap-2">
        {[0, 1, 2, 3, 4].map((index) => (
          <div key={index} className="flex flex-1 flex-col items-center gap-2">
            <Skeleton className="size-10 rounded-full" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-2.5 w-20" />
          </div>
        ))}
      </div>
    </section>
  );
}
