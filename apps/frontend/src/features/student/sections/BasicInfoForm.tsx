import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { Input, Select, useToast } from "@/components";

import type { BasicInfo, SectionStatus } from "../api/profileApi";
import { SectionShell } from "../components/SectionShell";
import {
  BRANCH_OPTIONS,
  DEGREE_OPTIONS,
  SECTIONS,
  TARGET_ROLE_OPTIONS,
  graduationYearOptions,
} from "../constants";
import { useSaveBasic } from "../hooks/useProfileSection";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";
import { basicInfoSchema, type BasicInfoForm as BasicInfoFormValues } from "../schemas/profileSchemas";

const META = SECTIONS[0];
const YEAR_OPTIONS = graduationYearOptions();

interface BasicInfoFormProps {
  data: BasicInfo;
  status: SectionStatus | undefined;
}

export function BasicInfoForm({ data, status }: BasicInfoFormProps) {
  const save = useSaveBasic();
  const { showToast } = useToast();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BasicInfoFormValues>({
    resolver: zodResolver(basicInfoSchema),
    defaultValues: {
      headline: data.headline ?? "",
      college: data.college ?? "",
      degree: data.degree ?? undefined,
      branch: data.branch ?? undefined,
      graduation_year: data.graduation_year ?? undefined,
      location: data.location ?? "",
      target_role: data.target_role ?? undefined,
    },
  });

  // The server normalizes what it stores (trimming, enum coercion), so the
  // form is re-seeded from the response rather than left showing raw input.
  useEffect(() => {
    reset({
      headline: data.headline ?? "",
      college: data.college ?? "",
      degree: data.degree ?? undefined,
      branch: data.branch ?? undefined,
      graduation_year: data.graduation_year ?? undefined,
      location: data.location ?? "",
      target_role: data.target_role ?? undefined,
    });
  }, [data, reset]);

  const onSubmit = handleSubmit((values) => {
    save.mutate(values, {
      onSuccess: () => showToast("Basic information saved.", "success"),
    });
  });

  return (
    <SectionShell
      meta={META}
      status={status}
      onSubmit={onSubmit}
      isSaving={save.isPending}
      errorMessage={save.isError ? getProfileErrorMessage(save.error) : null}
    >
      <Input
        label="Headline"
        placeholder="Final-year CS student building compilers"
        error={errors.headline?.message}
        {...register("headline")}
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <Input
          label="College"
          placeholder="IIT Bombay"
          error={errors.college?.message}
          {...register("college")}
        />
        <Input
          label="Location"
          placeholder="Mumbai, India"
          error={errors.location?.message}
          {...register("location")}
        />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <Select
          label="Degree"
          placeholder="Select your degree"
          options={DEGREE_OPTIONS}
          defaultValue=""
          error={errors.degree?.message}
          {...register("degree")}
        />
        <Select
          label="Branch"
          placeholder="Select your branch"
          options={BRANCH_OPTIONS}
          defaultValue=""
          error={errors.branch?.message}
          {...register("branch")}
        />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <Select
          label="Graduation year"
          placeholder="Select a year"
          options={YEAR_OPTIONS}
          defaultValue=""
          error={errors.graduation_year?.message}
          {...register("graduation_year")}
        />
        <Select
          label="Target role"
          placeholder="Select a target role"
          options={TARGET_ROLE_OPTIONS}
          defaultValue=""
          error={errors.target_role?.message}
          {...register("target_role")}
        />
      </div>
    </SectionShell>
  );
}
