import { Button, ErrorState, Skeleton } from "@/components";

import type { SectionKey } from "../api/profileApi";
import {
  useBasicSection,
  useCertificatesSection,
  useExperiencesSection,
  useProfileCompleteness,
  useProjectsSection,
  useTechnicalSection,
} from "../hooks/useProfileSection";
import { BasicInfoForm } from "./BasicInfoForm";
import { CertificatesForm } from "./CertificatesForm";
import { ExperienceForm } from "./ExperienceForm";
import { ProjectsForm } from "./ProjectsForm";
import { TechnicalForm } from "./TechnicalForm";

export function SectionSkeleton() {
  return (
    <div className="space-y-4 rounded-2xl border border-rule bg-white p-6">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-2/3" />
    </div>
  );
}

/**
 * Renders one of the five section forms.
 *
 * Extracted from `ProfileBuilderPage` so the setup flow's manual path and the
 * standalone builder render the identical form for a given section — the
 * manual path is explicitly "the existing per-section endpoints unchanged", and
 * a second copy of this switch would be the place that stopped being true.
 *
 * Only the active section's data is fetched: each `useQuery` is gated on
 * whether its step is showing, so opening either screen costs one completeness
 * call plus one section, not all five.
 */
export function ActiveSection({ section }: { section: SectionKey }) {
  const completeness = useProfileCompleteness();
  const status = completeness.data?.sections.find((item) => item.key === section);

  // Hooks must run unconditionally, so gating happens via `enabled` — only
  // the visible step actually issues a request.
  const basic = useBasicSection(section === "basic");
  const technical = useTechnicalSection(section === "technical");
  const projects = useProjectsSection(section === "projects");
  const certificates = useCertificatesSection(section === "certificates");
  const experiences = useExperiencesSection(section === "experience");

  const query = {
    basic,
    technical,
    projects,
    certificates,
    experience: experiences,
  }[section];

  if (query.isPending) return <SectionSkeleton />;
  if (query.isError) {
    return (
      <ErrorState
        title="Could not load this section"
        description="Something went wrong fetching your saved answers."
        action={
          <Button type="button" variant="secondary" size="sm" onClick={() => void query.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  switch (section) {
    case "basic":
      return <BasicInfoForm data={basic.data!.data} status={status} />;
    case "technical":
      return <TechnicalForm data={technical.data!.data} status={status} />;
    case "projects":
      return <ProjectsForm data={projects.data!.data} status={status} />;
    case "certificates":
      return <CertificatesForm data={certificates.data!.data} status={status} />;
    case "experience":
      return <ExperienceForm data={experiences.data!.data} status={status} />;
    default:
      return null;
  }
}
