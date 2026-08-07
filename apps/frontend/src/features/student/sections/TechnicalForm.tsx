import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Github, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { Button, Input, Select, useToast } from "@/components";

import type { CodingPlatformType, SectionStatus, TechnicalSection } from "../api/profileApi";
import { githubApi } from "../api/githubApi";
import { VerificationBadge } from "../components/SectionBadges";
import { SectionShell, type SectionNav } from "../components/SectionShell";
import { API_BACKED_PLATFORMS, CODING_PLATFORM_OPTIONS, SECTIONS } from "../constants";
import { useSaveTechnical } from "../hooks/useProfileSection";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";
import { setupApi } from "../setup/api/setupApi";
import { VerifyStatus, type VerifyState } from "../setup/components/VerifyStatus";
import { technicalSchema, type TechnicalForm as TechnicalFormValues } from "../schemas/profileSchemas";

const META = SECTIONS[1];
const ALL_PLATFORMS = CODING_PLATFORM_OPTIONS.map((option) => option.value as CodingPlatformType);

interface TechnicalFormProps {
  data: TechnicalSection;
  status: SectionStatus | undefined;
  nav?: SectionNav;
}

function toDefaults(data: TechnicalSection): TechnicalFormValues {
  return {
    github_username: data.github_account?.github_username ?? "",
    coding_profiles:
      data.coding_profiles.length > 0
        ? data.coding_profiles.map((account) => ({
            platform: account.platform,
            handle: account.handle,
            custom_platform_name: account.custom_platform_name ?? undefined,
            profile_url: account.platform === "other" ? account.profile_url : undefined,
          }))
        : [{ platform: "leetcode" as const, handle: "" }],
  };
}

/**
 * Step 3 of onboarding: the accounts GroundTruth checks.
 *
 * Every field here has a Verify button, and the section will not save until
 * each one has been checked. That is a deliberate departure from the other
 * four sections, which save whatever you type: a typo'd handle here is not a
 * cosmetic error, it is a claim that will fail verification hours later and
 * come back as a "we could not confirm this" email the student cannot connect
 * to a keystroke they no longer remember.
 *
 * "Checked" means the live probe returned `verified` **or** `unconfirmed` —
 * see `live_checks.py` for why most platforms cannot do better than the
 * latter. Only `failed` blocks, because only `failed` means the account was
 * not found at all.
 */
export function TechnicalForm({ data, status, nav }: TechnicalFormProps) {
  const save = useSaveTechnical();
  const { showToast } = useToast();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    getValues,
    formState: { errors },
  } = useForm<TechnicalFormValues>({
    resolver: zodResolver(technicalSchema),
    defaultValues: toDefaults(data),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "coding_profiles" });

  // Keyed by field-array id rather than index: removing a row shifts every
  // index after it, which would silently re-attribute one row's verification
  // result to its neighbour.
  const [githubState, setGithubState] = useState<VerifyState>({ phase: "idle" });
  const [profileStates, setProfileStates] = useState<Record<string, VerifyState>>({});

  useEffect(() => {
    reset(toDefaults(data));
    // Anything already stored has been through the background workers, so the
    // stored `verification_status` badge is the truthful summary and a stale
    // live-probe chip beside it would be a second, older opinion.
    setGithubState({ phase: "idle" });
    setProfileStates({});
  }, [data, reset]);

  const watched = watch("coding_profiles");
  const selectedPlatforms = watched?.map((item) => item?.platform) ?? [];
  const nextUnusedPlatform = ALL_PLATFORMS.find(
    // `other` stays available even when used: the unique constraint is per
    // platform, so a second "other" would collide — but the picker offering it
    // is how a student discovers the escape hatch at all.
    (platform) => platform === "other" || !selectedPlatforms.includes(platform),
  );

  const githubVerify = useMutation({ mutationFn: setupApi.verifyGithub });
  const profileVerify = useMutation({ mutationFn: setupApi.verifyCodingProfile });

  const connectGithub = useMutation({
    mutationFn: githubApi.connect,
    onSuccess: ({ authorize_url }) => {
      // A full-page navigation, not a popup: GitHub refuses to render its
      // consent screen in a frame, and a popup blocked by the browser is a
      // dead button with no error to show.
      window.location.assign(authorize_url);
    },
    onError: () => showToast("Could not start the GitHub connection. Try again.", "error"),
  });

  const runGithubCheck = useCallback(async () => {
    const username = getValues("github_username")?.trim();
    if (!username) {
      setGithubState({
        phase: "done",
        outcome: "failed",
        message: "Enter your GitHub username first.",
      });
      return;
    }
    setGithubState({ phase: "checking" });
    try {
      const result = await githubVerify.mutateAsync(username);
      setGithubState({ phase: "done", outcome: result.outcome, message: result.message });
    } catch (error) {
      setGithubState({ phase: "done", outcome: "failed", message: getProfileErrorMessage(error) });
    }
  }, [getValues, githubVerify]);

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

  /** Whether one row may be saved: already stored from a previous visit, or
   * checked just now with anything other than `failed`. */
  const isRowCleared = (fieldId: string, platform: CodingPlatformType, handle: string) => {
    const live = profileStates[fieldId];
    if (live?.phase === "done") return live.outcome !== "failed";
    const stored = statusByPlatform.get(platform);
    return stored !== undefined && stored.handle === handle;
  };

  const isGithubCleared = () => {
    if (githubState.phase === "done") return githubState.outcome !== "failed";
    const stored = data.github_account;
    return stored !== undefined && stored !== null && stored.github_username === getValues("github_username");
  };

  const onSubmit = handleSubmit((values) => {
    if (!isGithubCleared()) {
      setGithubState({
        phase: "done",
        outcome: "failed",
        message: "Verify this account before continuing.",
      });
      return;
    }

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
        github_username: values.github_username,
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
          showToast("Profiles saved and queued for verification.", "success");
          nav?.onSaved();
        },
      },
    );
  });

  return (
    <SectionShell
      meta={META}
      status={status}
      onSubmit={onSubmit}
      isSaving={save.isPending}
      errorMessage={save.isError ? getProfileErrorMessage(save.error) : null}
      nav={nav}
    >
      <div className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <Input
              label="GitHub profile URL or username"
              placeholder="https://github.com/ada"
              error={errors.github_username?.message}
              {...register("github_username")}
            />
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => void runGithubCheck()}
            isLoading={githubState.phase === "checking"}
            disabled={githubState.phase === "checking"}
          >
            Verify
          </Button>
        </div>

        <VerifyStatus state={githubState} />

        {data.github_account ? (
          <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--slate)]">
            <span className="font-mono">{data.github_account.profile_url}</span>
            <VerificationBadge status={data.github_account.verification_status} />
          </p>
        ) : null}

        {/* Offered whenever the account is not already OAuth-connected. The
            API check above proves the account exists; only this proves the
            student owns it, which is why it stays on screen rather than
            disappearing once the cheaper check passes. */}
        {data.github_account?.verification_source !== "github_oauth" ? (
          <div className="mt-3 border-t border-[var(--rule)] pt-3">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => connectGithub.mutate()}
              isLoading={connectGithub.isPending}
            >
              <Github size={14} aria-hidden="true" className="mr-1.5" />
              Connect with GitHub
            </Button>
            <p className="mt-1.5 text-xs text-[var(--slate)]">
              Optional, but it is the only way to prove the account is yours — and it unlocks the
              repository picker on the next step.
            </p>
          </div>
        ) : null}
      </div>

      <fieldset>
        <legend className="text-sm font-medium text-[var(--slate)]">Coding profiles</legend>
        <p className="mt-0.5 text-xs text-[var(--slate)]">
          At least one is required. Each has to be verified before you can continue.
        </p>

        <div className="mt-3 space-y-3">
          {fields.map((field, index) => {
            const platform = selectedPlatforms[index];
            const existing = platform ? statusByPlatform.get(platform) : undefined;
            const isOther = platform === "other";
            const canReachVerified = platform ? API_BACKED_PLATFORMS.includes(platform) : false;

            return (
              <div key={field.id} className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-3">
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
                      label="Username"
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
                    disabled={fields.length === 1}
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
                  <p className="mt-1.5 text-xs text-[var(--slate)]">
                    This platform has no public API, so we can only confirm the page exists.
                  </p>
                ) : null}

                {existing ? (
                  <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--slate)]">
                    <span className="font-mono">{existing.profile_url}</span>
                    <VerificationBadge status={existing.verification_status} />
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>

        {errors.coding_profiles?.root?.message ? (
          <p role="alert" className="mt-2 text-xs text-[var(--failed)]">
            {errors.coding_profiles.root.message}
          </p>
        ) : null}
        {errors.coding_profiles?.message ? (
          <p role="alert" className="mt-2 text-xs text-[var(--failed)]">
            {errors.coding_profiles.message}
          </p>
        ) : null}

        {nextUnusedPlatform ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => append({ platform: nextUnusedPlatform, handle: "" })}
          >
            <Plus size={14} aria-hidden="true" /> Add another platform
          </Button>
        ) : null}
      </fieldset>

      <p className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] px-3 py-2 text-xs text-[var(--slate)]">
        Verifying here only checks the account exists. The full analysis — contributions, ratings,
        solved counts — runs in the background after you submit, and these stay marked{" "}
        <span className="font-medium text-[var(--flagged)]">pending</span> until it finishes.
      </p>
    </SectionShell>
  );
}
