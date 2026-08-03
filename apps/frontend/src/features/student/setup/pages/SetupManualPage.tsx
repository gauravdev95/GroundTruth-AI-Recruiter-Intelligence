import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components";

import type { SectionKey } from "../../api/profileApi";
import { DiscoverabilityBanner } from "../../components/DiscoverabilityBanner";
import { useProfileCompleteness } from "../../hooks/useProfileSection";
import { ActiveSection } from "../../sections/ActiveSection";
import { SetupStepper, SetupStepperSkeleton } from "../components/SetupStepper";
import { useSetupState } from "../hooks/useSetupState";

/**
 * The manual path — the existing five section endpoints, unchanged.
 *
 * It renders the same `ActiveSection` the standalone builder does; the only
 * difference is the chrome around it, which is the setup flow's horizontal
 * stepper instead of the builder's sidebar.
 *
 * The starting step is seeded from `current_step_index` *once*, then owned
 * locally. Re-seeding on every refetch would drag a student back to step 1 the
 * moment they saved step 3 and the server's idea of "current" moved — the
 * server value is a starting hint, and every step stays clickable throughout.
 */
export function SetupManualPage() {
  const navigate = useNavigate();
  const setupState = useSetupState();
  const completeness = useProfileCompleteness();
  const [activeSection, setActiveSection] = useState<SectionKey | null>(null);

  const serverCurrent = setupState.data?.steps[setupState.data.current_step_index]?.key ?? null;

  useEffect(() => {
    if (activeSection === null && serverCurrent !== null) {
      setActiveSection(serverCurrent);
    }
  }, [activeSection, serverCurrent]);

  if (setupState.isError) {
    return (
      <ErrorState
        title="Could not load your profile setup"
        description="Something went wrong fetching your progress. Refresh to try again."
      />
    );
  }

  const isReady = setupState.data !== undefined && activeSection !== null;

  return (
    <div className="space-y-6">
      {!setupState.data ? (
        <SetupStepperSkeleton />
      ) : (
        <SetupStepper
          steps={setupState.data.steps}
          // Follows the student's selection once they have one, so clicking a
          // step visibly moves the pill rather than leaving it behind.
          currentStepIndex={
            setupState.data.steps.findIndex((step) => step.key === activeSection) === -1
              ? setupState.data.current_step_index
              : setupState.data.steps.findIndex((step) => step.key === activeSection)
          }
          completionPercentage={setupState.data.completion_percentage}
          onSelect={(step) => setActiveSection(step.key)}
        />
      )}

      <div className="flex items-center justify-between gap-3">
        <Link
          to="/student/profile/setup"
          className="inline-flex items-center gap-1.5 rounded-lg text-sm font-medium text-slate-500 transition hover:text-violet-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Back to setup
        </Link>
        {/* Switching is lossless in both directions: neither path clears the
            other's saved sections, and the resume flow writes only a draft
            until confirmed. */}
        <button
          type="button"
          onClick={() => navigate("/student/profile/setup/resume")}
          className="rounded-lg text-sm font-medium text-violet-700 underline-offset-4 transition hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500"
        >
          Upload a resume instead
        </button>
      </div>

      {completeness.data ? <DiscoverabilityBanner completeness={completeness.data} /> : null}

      {isReady ? <ActiveSection section={activeSection} /> : <Skeleton className="h-96 w-full rounded-2xl" />}
    </div>
  );
}
