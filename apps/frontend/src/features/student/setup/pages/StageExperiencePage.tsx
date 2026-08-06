import { Button, ErrorState } from "@/components";

import { useExperiencesSection, useProfileCompleteness } from "../../hooks/useProfileSection";
import { SectionSkeleton } from "../../sections/ActiveSection";
import { ExperienceForm } from "../../sections/ExperienceForm";
import { StageSkipBar } from "../components/StageShell";
import { useStageNav } from "../hooks/useStageNav";

/**
 * Stage 6 — experience. Optional, and the last stage before review.
 *
 * The skip here matters more than on the other two optional stages: a
 * first-year with no internships is a normal user of this product, and a
 * screen that makes them feel they are leaving something undone right before
 * submitting is the wrong last impression of onboarding.
 */
export function StageExperiencePage() {
  const { advance, goBack } = useStageNav();
  const experiences = useExperiencesSection();
  const completeness = useProfileCompleteness();
  const status = completeness.data?.sections.find((section) => section.key === "experience");

  if (experiences.isPending) return <SectionSkeleton />;
  if (experiences.isError) {
    return (
      <ErrorState
        title="Could not load this stage"
        description="Something went wrong fetching your saved experience."
        action={
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void experiences.refetch()}
          >
            Try again
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <ExperienceForm
        data={experiences.data.data}
        status={status}
        nav={{ onSaved: advance, onPrevious: goBack }}
      />
      <StageSkipBar label="Skip — I don't have any yet" />
    </div>
  );
}
