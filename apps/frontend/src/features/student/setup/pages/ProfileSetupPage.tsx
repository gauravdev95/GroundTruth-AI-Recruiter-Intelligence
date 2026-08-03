import { ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components";

import { useChooseOnboarding } from "../../hooks/useProfileSection";
import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { SetupFooterStrip } from "../components/SetupFooterStrip";
import { FillManuallyCard, UploadResumeCard } from "../components/SetupOptionCards";
import { SetupStepper, SetupStepperSkeleton } from "../components/SetupStepper";
import { useSetupState } from "../hooks/useSetupState";
import { useSetupUpload } from "../hooks/useSetupUpload";

/**
 * The profile setup entry screen — the first thing a student sees after signup.
 *
 * It offers two paths and commits to neither. Picking one navigates; it does
 * not write a decision the student has to live with. `useChooseOnboarding` is
 * fired alongside as telemetry — its result is never awaited and never read
 * back here, because a failed bookkeeping write must not strand a student on a
 * screen whose only job is to send them somewhere.
 *
 * Nothing renders from a default. While `setup-state` is in flight the stepper
 * and both cards are skeletons, because the alternative — drawing 0% and five
 * empty circles for a returning student — is a confident wrong answer.
 */
export function ProfileSetupPage() {
  const navigate = useNavigate();
  const setupState = useSetupState();
  const choose = useChooseOnboarding();
  const [rejection, setRejection] = useState<string | null>(null);
  const upload = useSetupUpload();

  function startResume(file: File) {
    setRejection(null);
    // Recorded, not awaited. See the note above.
    choose.mutate("resume_upload");
    upload.start(file);
    navigate("/student/profile/setup/resume");
  }

  function startManual() {
    choose.mutate("manual_entry");
    navigate("/student/profile/setup/manual");
  }

  if (setupState.isError) {
    return (
      <ErrorState
        title="Could not load your profile setup"
        description="Something went wrong fetching your progress. Refresh to try again."
      />
    );
  }

  const uploadError = rejection ?? (upload.error ? getProfileErrorMessage(upload.error) : null);

  return (
    <div className="space-y-6">
      {setupState.isPending || !setupState.data ? (
        <SetupStepperSkeleton />
      ) : (
        <SetupStepper
          steps={setupState.data.steps}
          currentStepIndex={setupState.data.current_step_index}
          completionPercentage={setupState.data.completion_percentage}
        />
      )}

      <header className="mx-auto max-w-2xl pt-2 text-center">
        <h1 className="flex items-center justify-center gap-2 font-display text-2xl font-bold text-slate-900 sm:text-[28px]">
          <Sparkles size={22} className="shrink-0 text-violet-500" aria-hidden="true" />
          Complete Your AI Verified Profile
        </h1>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-slate-500">
          Build your professional identity and increase your visibility to top recruiters.
        </p>
        <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-slate-500">
          <ShieldCheck size={14} className="shrink-0 text-violet-500" aria-hidden="true" />
          Your data is secure and only visible to verified companies.
        </p>
      </header>

      <div className="flex items-center gap-4 pt-2">
        <span aria-hidden="true" className="h-px flex-1 bg-violet-100" />
        <h2 className="shrink-0 text-xs font-semibold text-slate-600">
          How would you like to create your profile?
        </h2>
        <span aria-hidden="true" className="h-px flex-1 bg-violet-100" />
      </div>

      {setupState.isPending ? (
        <div className="grid items-stretch gap-5 md:grid-cols-2">
          <Skeleton className="h-[30rem] w-full rounded-2xl" />
          <Skeleton className="h-[30rem] w-full rounded-2xl" />
        </div>
      ) : (
        <div className="grid items-stretch gap-5 md:grid-cols-2">
          <UploadResumeCard
            onFile={startResume}
            onReject={setRejection}
            isUploading={upload.isUploading}
            error={uploadError}
          />
          <FillManuallyCard onStart={startManual} />
        </div>
      )}

      <SetupFooterStrip />
    </div>
  );
}
