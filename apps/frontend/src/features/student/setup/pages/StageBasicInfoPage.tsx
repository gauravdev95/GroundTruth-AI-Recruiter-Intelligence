import { Button, ErrorState } from "@/components";

import { SectionSkeleton } from "../../sections/ActiveSection";
import { BasicInfoForm } from "../../sections/BasicInfoForm";
import { useBasicSection, useProfileCompleteness } from "../../hooks/useProfileSection";
import { useStageNav } from "../hooks/useStageNav";
import { stageByStepKey } from "../lib/stages";

const STAGE = stageByStepKey("basic")!;

/**
 * Stage 1 — basic info.
 *
 * A thin route wrapper: the form itself is `BasicInfoForm`, shared verbatim
 * with the standalone profile editor, so the fields a student fills at
 * onboarding and the fields they edit afterwards cannot drift apart. Only the
 * chrome differs, and that arrives through `nav`.
 *
 * The progress bar is rendered by the form's own `SectionShell` parent rather
 * than here — see `StageShell` for why stages that own a form skip it.
 */
export function StageBasicInfoPage() {
  const { advance, goBack } = useStageNav();
  const basic = useBasicSection();
  const completeness = useProfileCompleteness();
  const status = completeness.data?.sections.find((section) => section.key === "basic");

  if (basic.isPending) return <SectionSkeleton />;
  if (basic.isError) {
    return (
      <ErrorState
        title="Could not load this stage"
        description="Something went wrong fetching your saved answers."
        action={
          <Button type="button" variant="secondary" size="sm" onClick={() => void basic.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  return (
    <BasicInfoForm
      data={basic.data.data}
      status={status}
      // `onSaved` fires only from the mutation's `onSuccess`, so a failed save
      // leaves the student here with their input and the error rather than one
      // stage further on with neither.
      nav={{ onSaved: advance, onPrevious: goBack }}
    />
  );
}

export { STAGE as BASIC_INFO_STAGE };
