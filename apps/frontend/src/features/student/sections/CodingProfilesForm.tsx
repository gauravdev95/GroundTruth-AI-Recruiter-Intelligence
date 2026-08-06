import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { Button, Input, Select, useToast } from "@/components";

import type { CodingPlatformType, SectionStatus, TechnicalSection } from "../api/profileApi";
import { VerificationBadge } from "../components/SectionBadges";
import { SectionShell, type SectionNav } from "../components/SectionShell";
import { API_BACKED_PLATFORMS, CODING_PLATFORM_OPTIONS } from "../constants";
import { useSaveCodingProfiles } from "../hooks/useProfileSection";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";
import { setupApi } from "../setup/api/setupApi";
import { VerifyStatus, type VerifyState } from "../setup/components/VerifyStatus";
import type { OnboardingStage } from "../setup/lib/stages";
import {
  codingProfilesSchema,
  type CodingProfilesForm as CodingProfilesFormValues,
} from "../schemas/profileSchemas";

const ALL_PLATFORMS = CODING_PLATFORM_OPTIONS.map((option) => option.value as CodingPlatformType);

interface CodingProfilesFormProps {
  data: TechnicalSection;
  status: SectionStatus | undefined;
  stage: OnboardingStage;
  nav?: SectionNav;
}

function toDefaults(data: TechnicalSection): CodingProfilesFormValues {
  return {
    coding_profiles: data.coding_profiles.map((account) => ({
      platform: account.platform,
      handle: account.handle,
      custom_platform_name: account.custom_platform_name ?? undefined,
      profile_url: account.platform === "other" ? account.profile_url : undefined,
    })),
  };
}

/**
 * Onboarding stage 4 — coding profiles alone.
 *
 * Split out of `TechnicalForm` rather than added to it as a flag. That form is
 * still the right thing for the profile editor and the resume-confirm path,
 * where GitHub and the handles are saved together; this one exists because the
 * onboarding stage saves the handles *without* being able to disturb the
 * GitHub account connected on the previous stage.
 *
 * **It starts with zero rows, and saving zero rows is valid.** `TechnicalForm`
 * seeds an empty row because a handle was mandatory there. Here an empty form
 * is the honest starting state for an optional stage — pre-filling a row would
 * present an obligation the stage does not have — and an empty save is what
 * clears handles a student no longer wants.
 *
 * **Verification still gates a row that has content.** A typo'd handle is not
 * a cosmetic error: it is a claim that fails hours later and returns as a "we
 * could not confirm this" email the student cannot connect to a keystroke.
 * Skipping the stage entirely is free; entering a handle and not checking it
 * is not.
 */
export function CodingProfilesForm({ data, status, stage, nav }: CodingProfilesFormProps) {
  const save = useSaveCodingProfiles();
  const { showToast } = useToast();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    getValues,
    formState: { errors },
  } = useForm<CodingProfilesFormValues>({
    resolver: zodResolver(codingProfilesSchema),
    defaultValues: toDefaults(data),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "coding_profiles" });

  // Keyed by field-array id rather than index: removing a row shifts every
  // index after it, which would re-attribute one row's verification result to
  // its neighbour.
  const [profileStates, setProfileStates] = useState<Record<string, VerifyState>>({});

  useEffect(() => {
    reset(toDefaults(data));
    // Anything already stored has been through the background workers, so the
    // stored badge is the truthful summary and a stale live-probe chip beside
    // it would be a second, older opinion.
    setProfileStates({});
  }, [data, reset]);

  const watched = watch("coding_profiles");
  const selectedPlatforms = watched?.map((item) => item?.platform) ?? [];
  const nextUnusedPlatform = ALL_PLATFORMS.find(
    // `other` stays available even when used — the unique constraint is per
    // platform, but offering it is how a student finds the escape hatch.
    (platform) => platform === "other" || !selectedPlatforms.includes(platform),
  );

  const profileVerify = useMutation({ mutationFn: setupApi.verifyCodingProfile });

  const runProfileCheck = useCallback(
    async (fieldId: string, index: number) => {
      const item = getValues(`coding_profiles.${index}` as const);
      if (!item?.handle?.trim()) {
        setProfileStates((prev) => ({
          ...prev,
          [fieldId]: { phase: "done", outcome: "failed", message: "Enter a handle first." },
        }));
        return;
      }
      setProfileStates((prev) => ({ ...prev, [fieldId]: { phase: "checking" } }));
      try {
        const result = await profileVerify.mutateAsync({
          platform: item.platform,
          handle: item.handle,
          profile_url: item.profile_url || null,
        });
        setProfileStates((prev) => ({
          ...prev,
          [fieldId]: { phase: "done", outcome: result.outcome, message: result.message },
        }));
      } catch (error) {
        setProfileStates((prev) => ({
          ...prev,
          [fieldId]: { phase: "done", outcome: "failed", message: getProfileErrorMessage(error) },
        }));
      }
    },
    [getValues, profileVerify],
  );

  const statusByPlatform = new Map(data.coding_profiles.map((account) => [account.platform, account]));

  /** Already stored from a previous visit, or checked just now with anything
   * other than `failed`. */
  const isRowCleared = (fieldId: string, platform: CodingPlatformType, handle: string) => {
    const live = profileStates[fieldId];
    if (live?.phase === "done") return live.outcome !== "failed";
    const stored = statusByPlatform.get(platform);
    return stored !== undefined && stored.handle === handle;
  };

  const onSubmit = handleSubmit((values) => {
    const unchecked = fields.findIndex(
      (field, index) =>
        !isRowCleared(field.id, values.coding_profiles[index].platform, values.coding_profiles[index].handle),
    );
    if (unchecked !== -1) {
      setProfileStates((prev) => ({
        ...prev,
        [fields[unchecked].id]: {
          phase: "done",
          outcome: "failed",
          message: "Verify this profile before continuing.",
        },
      }));
      return;
    }

    save.mutate(
      {
        coding_profiles: values.coding_profiles.map((item) => ({
          platform: item.platform,
          handle: item.handle,
          // Both are rejected outright by the server for a named platform, so
          // they are sent only where they are meaningful.
          custom_platform_name: item.platform === "other" ? item.custom_platform_name : undefined,
          profile_url: item.platform === "other" ? item.profile_url : undefined,
        })),
      },
      {
        onSuccess: () => {
          showToast(
            values.coding_profiles.length === 0
              ? "No coding profiles saved."
              : "Profiles saved and queued for verification.",
            "success",
          );
          nav?.onSaved();
        },
      },
    );
  });

  return (
    <SectionShell
      meta={{
        key: "technical",
        title: "Coding profile",
        description:
          "Optional — helps us ask better interview questions. It does not count as a verified skill on its own.",
        isMandatory: stage.isMandatory,
      }}
      status={status}
      onSubmit={onSubmit}
      isSaving={save.isPending}
      errorMessage={save.isError ? getProfileErrorMessage(save.error) : null}
      nav={nav}
    >
      {fields.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule bg-panel px-4 py-6 text-center text-sm text-slate-500">
          Nothing here yet. Add a platform below, or skip this stage.
        </p>
      ) : null}

      <div className="space-y-3">
        {fields.map((field, index) => {
          const platform = selectedPlatforms[index];
          const existing = platform ? statusByPlatform.get(platform) : undefined;
          const isOther = platform === "other";
          const canReachVerified = platform ? API_BACKED_PLATFORMS.includes(platform) : false;

          return (
            <div key={field.id} className="rounded-xl border border-rule bg-panel p-3">
              <div className="flex flex-wrap items-end gap-3">
                <div className="w-44 shrink-0">
                  <Select
                    label="Platform"
                    options={CODING_PLATFORM_OPTIONS}
                    error={errors.coding_profiles?.[index]?.platform?.message}
                    {...register(`coding_profiles.${index}.platform` as const)}
                  />
                </div>
                <div className="min-w-[160px] flex-1">
                  <Input
                    label="Profile URL or handle"
                    placeholder="your_handle"
                    error={errors.coding_profiles?.[index]?.handle?.message}
                    {...register(`coding_profiles.${index}.handle` as const)}
                  />
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void runProfileCheck(field.id, index)}
                  isLoading={profileStates[field.id]?.phase === "checking"}
                  disabled={profileStates[field.id]?.phase === "checking"}
                >
                  Verify
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => remove(index)}
                  aria-label={`Remove profile ${index + 1}`}
                  className="mb-1"
                >
                  <Trash2 size={16} aria-hidden="true" />
                </Button>
              </div>

              {isOther ? (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Input
                    label="Platform name"
                    placeholder="TopCoder"
                    error={errors.coding_profiles?.[index]?.custom_platform_name?.message}
                    {...register(`coding_profiles.${index}.custom_platform_name` as const)}
                  />
                  <Input
                    label="Profile URL"
                    placeholder="https://topcoder.com/members/ada"
                    error={errors.coding_profiles?.[index]?.profile_url?.message}
                    {...register(`coding_profiles.${index}.profile_url` as const)}
                  />
                </div>
              ) : null}

              <VerifyStatus state={profileStates[field.id] ?? { phase: "idle" }} />

              {!canReachVerified && platform ? (
                <p className="mt-1.5 text-xs text-slate-500">
                  This platform has no public API, so we can only confirm the page exists.
                </p>
              ) : null}

              {existing ? (
                <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span className="font-mono">{existing.profile_url}</span>
                  <VerificationBadge status={existing.verification_status} />
                </p>
              ) : null}
            </div>
          );
        })}
      </div>

      {nextUnusedPlatform ? (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => append({ platform: nextUnusedPlatform, handle: "" })}
        >
          <Plus size={14} aria-hidden="true" /> Add {fields.length === 0 ? "a" : "another"} platform
        </Button>
      ) : null}

      <p className="rounded-xl border border-rule bg-panel px-3 py-2 text-xs leading-relaxed text-slate-500">
        These appear on your profile under <span className="font-medium">Supporting Signals</span>,
        separate from verified skills. A rating is evidence that you practise, not evidence that you
        built something — so it never merges into your verified-skill percentages.
      </p>
    </SectionShell>
  );
}
