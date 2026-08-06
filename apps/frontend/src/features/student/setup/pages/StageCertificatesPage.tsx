import { Button, ErrorState } from "@/components";

import { useCertificatesSection, useProfileCompleteness } from "../../hooks/useProfileSection";
import { SectionSkeleton } from "../../sections/ActiveSection";
import { CertificatesForm } from "../../sections/CertificatesForm";
import { StageSkipBar } from "../components/StageShell";
import { useStageNav } from "../hooks/useStageNav";

/**
 * Stage 5 — certificates. Optional.
 *
 * Wraps the shared form so what a student enters at onboarding and what they
 * edit afterwards is the same screen. The only addition is the explicit skip.
 */
export function StageCertificatesPage() {
  const { advance, goBack } = useStageNav();
  const certificates = useCertificatesSection();
  const completeness = useProfileCompleteness();
  const status = completeness.data?.sections.find((section) => section.key === "certificates");

  if (certificates.isPending) return <SectionSkeleton />;
  if (certificates.isError) {
    return (
      <ErrorState
        title="Could not load this stage"
        description="Something went wrong fetching your saved certificates."
        action={
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void certificates.refetch()}
          >
            Try again
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <CertificatesForm
        data={certificates.data.data}
        status={status}
        nav={{ onSaved: advance, onPrevious: goBack }}
      />
      <StageSkipBar />
    </div>
  );
}
