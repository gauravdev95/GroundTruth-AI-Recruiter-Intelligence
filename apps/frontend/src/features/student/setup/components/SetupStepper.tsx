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
 * The flow overview shown on the two entry screens — the resume-or-manual fork
 * and the resume upload page.
 *
 * **This is not the same component as `SetupProgressBar`, and the difference
 * is which number each one shows.** The stage pages show *position in the
 * flow*, a client-known constant per stage. This one shows the server's
 * `profile_strength`, which is what a returning student actually wants on an
 * overview: how complete their profile is, not how far along a form they are.
 *
 * Because both can appear within a click of each other, the pill here names
 * its number explicitly ("35% profile strength"). An unlabelled percentage
 * beside a differently-computed unlabelled percentage is two numbers the
 * student has no way to tell apart.
 *
 * A separate component from `ProfileStepper` rather than a variant of it: that
 * one is a vertical sidebar list of buttons inside the builder, this is a
 * horizontal card that collapses to a "Step N of 8" strip on mobile. Sharing
 * one component would mean two layouts behind a flag and neither read clearly.
 *
 * The count comes from `steps.length`, never a literal — the server owns how
 * many steps there are, and a hardcoded number here would be the thing that
 * stayed behind when the flow grew from seven steps to eight.
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
      className="rounded-2xl border border-[var(--violet)]/25 bg-[var(--panel)] p-5 shadow-sm shadow-[var(--shadow-panel)] sm:p-6"
    >
      <div className="mb-5 flex items-start justify-between gap-3">
        <h2 className="font-display text-sm font-semibold text-[var(--ink)]">Your progress</h2>
        <span className="shrink-0 rounded-full bg-[var(--violet)]/10 px-3 py-1 text-xs font-semibold text-[var(--violet)]">
          {completionPercentage}% profile strength
        </span>
      </div>

      {/* Mobile: an eight-across layout cannot survive a 360px viewport without
          truncating every label to uselessness, so it collapses to the one
          fact that matters — which step you are on and what it is called. */}
      <div className="md:hidden">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--violet)]">
          Step {currentStepIndex + 1} of {steps.length}
        </p>
        <p className="mt-1 text-sm font-semibold text-[var(--ink)]">{current?.title}</p>
        <p className="mt-0.5 text-xs text-[var(--slate)]">{current?.subtitle}</p>
        <div
          className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[var(--violet)]/15"
          role="progressbar"
          aria-valuenow={completionPercentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Profile strength"
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-[var(--violet)] to-[var(--blue)] transition-[width] duration-500"
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
                      "transition hover:bg-[var(--violet)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--violet)]",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition",
                      isActive
                        ? "border-[var(--violet)] bg-gradient-to-br from-[var(--violet)] to-[var(--blue)] text-white shadow-md shadow-[var(--shadow-panel)]"
                        : isComplete
                          ? "border-[var(--violet)]/30 bg-[var(--violet)]/10 text-[var(--violet)]"
                          : "border-[var(--rule)] bg-[var(--panel)] text-[var(--muted)]",
                    )}
                  >
                    {isComplete && !isActive ? <Check size={18} strokeWidth={3} /> : index + 1}
                  </span>

                  <span
                    className={cn(
                      "mt-2.5 block text-xs font-semibold leading-snug",
                      isActive ? "text-[var(--ink)]" : isComplete ? "text-[var(--slate)]" : "text-[var(--muted)]",
                    )}
                  >
                    {step.title}
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-[var(--muted)]">
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
                  <span className="mt-2 rounded-full bg-[var(--violet)]/15 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--violet)]">
                    Current Step
                  </span>
                ) : null}
              </div>

              {index < steps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "mt-5 h-0 flex-1 shrink-0 border-t-2 border-dotted",
                    isComplete ? "border-[var(--violet)]/40" : "border-[var(--rule)]",
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
      className="rounded-2xl border border-[var(--violet)]/25 bg-[var(--panel)] p-5 shadow-sm shadow-[var(--shadow-panel)] sm:p-6"
    >
      <div className="mb-5 flex items-center justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-6 w-28 rounded-full" />
      </div>
      <div className="flex items-start justify-between gap-2">
        {[0, 1, 2, 3, 4, 5, 6, 7].map((index) => (
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
