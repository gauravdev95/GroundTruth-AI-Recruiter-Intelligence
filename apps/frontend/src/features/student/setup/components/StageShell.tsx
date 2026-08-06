import type { ReactNode } from "react";

import { Button } from "@/components";

import { useStageNav } from "../hooks/useStageNav";
import type { OnboardingStage } from "../lib/stages";

/**
 * The card chrome for a stage that does **not** own a section form.
 *
 * Stages 2, 3 and 7 (GitHub, projects, review) render custom content and use
 * this. Stages 1, 4, 5 and 6 render a shared section form, which brings its own
 * `SectionShell` card and heading — wrapping those in this one too would nest
 * two bordered cards with two headings saying the same thing.
 *
 * The progress bar is deliberately *not* here. It lives in `SetupStageLayout`
 * so it mounts once for the whole flow and does not repaint between stages —
 * a header that re-renders on navigation reads as a page reload, and a page
 * reload mid-setup reads as "did I just lose that?".
 */
export function StageShell({
  stage,
  title,
  description,
  children,
}: {
  stage: OnboardingStage;
  title: string;
  description: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-rule bg-white p-6">
      <header className="mb-5 border-b border-rule pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-lg font-semibold text-ink">{title}</h1>
          <span
            className={
              stage.isMandatory
                ? "text-xs font-medium text-flagged"
                : "text-xs font-medium text-slate-400"
            }
          >
            {stage.isMandatory ? "Required" : "Optional"}
          </span>
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{description}</p>
      </header>

      {children}
    </section>
  );
}

/**
 * The explicit skip control for an optional stage.
 *
 * **A real button, not merely an absence of required fields.** A stage the
 * student may leave blank still reads as an obligation when the only way past
 * it is the same "Save & Next" the mandatory stages use — that button says
 * save, and there is nothing to save. Naming the action is what makes optional
 * legible as optional, and it is why every optional stage renders this even
 * though `advance` would do the same navigation.
 */
export function StageSkipBar({ label = "Skip for now" }: { label?: string }) {
  const { skip } = useStageNav();

  return (
    <div className="flex justify-center">
      <Button type="button" variant="ghost" onClick={skip}>
        {label}
      </Button>
    </div>
  );
}
