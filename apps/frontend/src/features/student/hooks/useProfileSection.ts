import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import {
  profileApi,
  type BasicInfo,
  type BasicInfoPayload,
  type CertificatesPayload,
  type CertificatesSection,
  type CodingProfilesPayload,
  type ExperiencesPayload,
  type ExperiencesSection,
  type OnboardingChoice,
  type ProfileCompleteness,
  type ProjectsPayload,
  type ProjectsSection,
  type SectionCacheKey,
  type SectionEnvelope,
  type TechnicalPayload,
  type TechnicalSection,
} from "../api/profileApi";

/**
 * Every PUT returns the recomputed completeness alongside the saved section,
 * so a successful save seeds the completeness cache directly instead of
 * triggering a refetch. That is what keeps the strength meter and the
 * discoverability banner from briefly showing a stale score after a save.
 */
function useSectionMutation<TPayload, TData>(
  section: SectionCacheKey,
  mutationFn: (payload: TPayload) => Promise<SectionEnvelope<TData>>,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.studentProfile.section(section), result);
      queryClient.setQueryData(queryKeys.studentProfile.completeness(), result.completeness);
      // Invalidated rather than seeded: the PUT returns completeness, but
      // setup-state additionally derives `current_step_index` and the resume
      // state, so the server has to recompute it. Refetching is what keeps the
      // stepper's percentage a server value instead of a client guess.
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentProfile.setupState() });
    },
  });
}

export function useProfileCompleteness(): UseQueryResult<ProfileCompleteness> {
  return useQuery({
    queryKey: queryKeys.studentProfile.completeness(),
    queryFn: profileApi.completeness,
  });
}

/**
 * Records which lane the student picked at the setup fork.
 *
 * Telemetry, not routing. Nothing reads `onboarding_choice` to decide where a
 * student may go — the setup gates key on `meets_section_requirements` — so
 * this mutation's result is fired and forgotten, and a failed write costs a
 * data point rather than stranding anyone. Both paths stay open either way.
 */
export function useChooseOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (choice: OnboardingChoice) => profileApi.chooseOnboarding(choice),
    onSuccess: (completeness) => {
      queryClient.setQueryData(queryKeys.studentProfile.completeness(), completeness);
    },
  });
}

/** Hooks take `enabled` so the builder can fetch only the step being shown —
 * opening the page costs one completeness call plus one section, not five. */
export function useBasicSection(enabled = true) {
  return useQuery({
    queryKey: queryKeys.studentProfile.section("basic"),
    queryFn: profileApi.getBasic,
    enabled,
  });
}

export function useSaveBasic() {
  return useSectionMutation<BasicInfoPayload, BasicInfo>("basic", profileApi.saveBasic);
}

export function useTechnicalSection(enabled = true) {
  return useQuery({
    queryKey: queryKeys.studentProfile.section("technical"),
    queryFn: profileApi.getTechnical,
    enabled,
  });
}

export function useSaveTechnical() {
  return useSectionMutation<TechnicalPayload, TechnicalSection>("technical", profileApi.saveTechnical);
}

/**
 * Onboarding stage 4's writer. Seeds the same `technical` cache entry as
 * `useSaveTechnical` — the endpoint returns the whole technical envelope, so
 * one cache holds one copy of a resource that has two writers. Two entries
 * would each hold half of an overlapping payload and go stale through the
 * other.
 */
export function useSaveCodingProfiles() {
  return useSectionMutation<CodingProfilesPayload, TechnicalSection>(
    "technical",
    profileApi.saveCodingProfiles,
  );
}

export function useProjectsSection(enabled = true) {
  return useQuery({
    queryKey: queryKeys.studentProfile.section("projects"),
    queryFn: profileApi.getProjects,
    enabled,
  });
}

export function useSaveProjects() {
  return useSectionMutation<ProjectsPayload, ProjectsSection>("projects", profileApi.saveProjects);
}

export function useCertificatesSection(enabled = true) {
  return useQuery({
    queryKey: queryKeys.studentProfile.section("certificates"),
    queryFn: profileApi.getCertificates,
    enabled,
  });
}

export function useSaveCertificates() {
  return useSectionMutation<CertificatesPayload, CertificatesSection>(
    "certificates",
    profileApi.saveCertificates,
  );
}

export function useExperiencesSection(enabled = true) {
  return useQuery({
    queryKey: queryKeys.studentProfile.section("experience"),
    queryFn: profileApi.getExperiences,
    enabled,
  });
}

export function useSaveExperiences() {
  return useSectionMutation<ExperiencesPayload, ExperiencesSection>(
    "experience",
    profileApi.saveExperiences,
  );
}
