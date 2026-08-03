import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { Button, Input, Select, useToast } from "@/components";

import type { CodingPlatformType, SectionStatus, TechnicalSection } from "../api/profileApi";
import { VerificationBadge } from "../components/SectionBadges";
import { SectionShell } from "../components/SectionShell";
import { CODING_PLATFORM_OPTIONS, SECTIONS } from "../constants";
import { useSaveTechnical } from "../hooks/useProfileSection";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";
import { technicalSchema, type TechnicalForm as TechnicalFormValues } from "../schemas/profileSchemas";

const META = SECTIONS[1];
const ALL_PLATFORMS = CODING_PLATFORM_OPTIONS.map((option) => option.value as CodingPlatformType);

interface TechnicalFormProps {
  data: TechnicalSection;
  status: SectionStatus | undefined;
}

function toDefaults(data: TechnicalSection): TechnicalFormValues {
  return {
    github_username: data.github_account?.github_username ?? "",
    coding_profiles:
      data.coding_profiles.length > 0
        ? data.coding_profiles.map((account) => ({
            platform: account.platform,
            handle: account.handle,
          }))
        : [{ platform: "leetcode" as const, handle: "" }],
  };
}

export function TechnicalForm({ data, status }: TechnicalFormProps) {
  const save = useSaveTechnical();
  const { showToast } = useToast();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<TechnicalFormValues>({
    resolver: zodResolver(technicalSchema),
    defaultValues: toDefaults(data),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "coding_profiles" });

  useEffect(() => {
    reset(toDefaults(data));
  }, [data, reset]);

  const selectedPlatforms = watch("coding_profiles")?.map((item) => item?.platform) ?? [];
  const nextUnusedPlatform = ALL_PLATFORMS.find((platform) => !selectedPlatforms.includes(platform));

  const onSubmit = handleSubmit((values) => {
    save.mutate(values, {
      onSuccess: () => showToast("Technical profiles saved and queued for verification.", "success"),
    });
  });

  const statusByPlatform = new Map(data.coding_profiles.map((account) => [account.platform, account]));

  return (
    <SectionShell
      meta={META}
      status={status}
      onSubmit={onSubmit}
      isSaving={save.isPending}
      errorMessage={save.isError ? getProfileErrorMessage(save.error) : null}
    >
      <div>
        <Input
          label="GitHub username or profile URL"
          placeholder="ada  ·  or  ·  https://github.com/ada"
          error={errors.github_username?.message}
          {...register("github_username")}
        />
        {data.github_account ? (
          <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="font-mono">{data.github_account.profile_url}</span>
            <VerificationBadge status={data.github_account.verification_status} />
          </p>
        ) : null}
      </div>

      <fieldset>
        <legend className="text-sm font-medium text-slate-700">
          Competitive programming profiles
        </legend>
        <p className="mt-0.5 text-xs text-slate-500">At least one is required.</p>

        <div className="mt-3 space-y-3">
          {fields.map((field, index) => {
            const platform = selectedPlatforms[index];
            const existing = platform ? statusByPlatform.get(platform) : undefined;

            return (
              <div key={field.id} className="rounded-xl border border-rule bg-panel p-3">
                <div className="flex items-end gap-3">
                  <div className="w-44 shrink-0">
                    <Select
                      label="Platform"
                      options={CODING_PLATFORM_OPTIONS}
                      error={errors.coding_profiles?.[index]?.platform?.message}
                      {...register(`coding_profiles.${index}.platform` as const)}
                    />
                  </div>
                  <div className="flex-1">
                    <Input
                      label="Handle"
                      placeholder="your_handle"
                      error={errors.coding_profiles?.[index]?.handle?.message}
                      {...register(`coding_profiles.${index}.handle` as const)}
                    />
                  </div>
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

        {errors.coding_profiles?.root?.message ? (
          <p role="alert" className="mt-2 text-xs text-red-500">
            {errors.coding_profiles.root.message}
          </p>
        ) : null}
        {errors.coding_profiles?.message ? (
          <p role="alert" className="mt-2 text-xs text-red-500">
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

      <p className="rounded-xl border border-rule bg-panel px-3 py-2 text-xs text-slate-500">
        Saving queues these accounts for verification. They stay marked{" "}
        <span className="font-medium text-flagged">pending</span> until GroundTruth has checked them —
        saving a profile is not the same as proving it.
      </p>
    </SectionShell>
  );
}
