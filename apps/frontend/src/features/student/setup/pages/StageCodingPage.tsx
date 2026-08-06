import { Button, ErrorState } from "@/components";

import { useProfileCompleteness, useTechnicalSection } from "../../hooks/useProfileSection";
import { SectionSkeleton } from "../../sections/ActiveSection";
import { CodingProfilesForm } from "../../sections/CodingProfilesForm";
import { StageSkipBar } from "../components/StageShell";
import { useStageNav } from "../hooks/useStageNav";
import { stageByStepKey } from "../lib/stages";

const STAGE = stageByStepKey("coding")!;

/**
 * Stage 4 — coding profiles. Optional.
 *
 * The header states the limit of what this data is for, because the rest of
 * the product is built on the difference: a Codeforces rating is a supporting
 * signal that helps the interview ask better questions, and it is never a
 * verified skill. It is rendered under "Supporting Signals" on the evidence
 * report for the same reason, never merged into verified-skill percentages.
 */
export function StageCodingPage() {
  const { advance, goBack } = useStageNav();
  const technical = useTechnicalSection();
  const completeness = useProfileCompleteness();
  const status = completeness.data?.sections.find((section) => section.key === "coding");

  if (technical.isPending) return <SectionSkeleton />;
  if (technical.isError) {
    return (
      <ErrorState
        title="Could not load this stage"
        description="Something went wrong fetching your saved handles."
        action={
          <Button type="button" variant="secondary" size="sm" onClick={() => void technical.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <CodingProfilesForm
        data={technical.data.data}
        status={status}
        stage={STAGE}
        nav={{ onSaved: advance, onPrevious: goBack }}
      />
      <StageSkipBar />
    </div>
  );
}
