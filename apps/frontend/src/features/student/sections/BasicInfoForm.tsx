import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Input, Select, useToast } from "@/components";

import type { BasicInfo, SectionStatus } from "../api/profileApi";
import { ProfilePhotoField } from "../components/ProfilePhotoField";
import { SectionShell, type SectionNav } from "../components/SectionShell";
import { TargetRolesField } from "../components/TargetRolesField";
import {
  BRANCH_OPTIONS,
  DEGREE_OPTIONS,
  SECTIONS,
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
  /** Present only inside the onboarding wizard. See `SectionShell`. */
  nav?: SectionNav;
}

export function BasicInfoForm({ data, status, nav }: BasicInfoFormProps) {
  const save = useSaveBasic();
  const { showToast } = useToast();

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BasicInfoFormValues>({
    resolver: zodResolver(basicInfoSchema),
    defaultValues: {
      full_name: data.full_name ?? "",
      phone_number: data.phone_number ?? "",
      headline: data.headline ?? "",
      college: data.college ?? "",
      degree: data.degree ?? undefined,
      branch: data.branch ?? undefined,
      graduation_year: data.graduation_year ?? undefined,
      location: data.location ?? "",
      target_roles: data.target_roles ?? [],
      about: data.about ?? "",
    },
  });

  // The server normalizes what it stores (trimming, enum coercion), so the
  // form is re-seeded from the response rather than left showing raw input.
  useEffect(() => {
    reset({
      full_name: data.full_name ?? "",
      phone_number: data.phone_number ?? "",
      headline: data.headline ?? "",
      college: data.college ?? "",
      degree: data.degree ?? undefined,
      branch: data.branch ?? undefined,
      graduation_year: data.graduation_year ?? undefined,
      location: data.location ?? "",
      target_roles: data.target_roles ?? [],
      about: data.about ?? "",
    });
  }, [data, reset]);

  const onSubmit = handleSubmit((values) => {
    save.mutate(values, {
      onSuccess: () => {
        showToast("Basic information saved.", "success");
        // Advancing only from `onSuccess` is what makes "Save & Next" honest:
        // a failed save leaves the student on the step with their input and
        // the error, never one screen further on with neither.
        nav?.onSaved();
      },
    });
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
      {/* Saves on its own the moment a file is picked — it is a multipart
          upload, not part of this form's JSON body. */}
      <ProfilePhotoField hasPhoto={data.has_profile_photo} />

      {/* First thing among the typed fields, because signup no longer asks
          for it — for most students this is where the platform learns their
          name. */}
      <Input
        label="Full name"
        autoComplete="name"
        placeholder="Ada Lovelace"
        error={errors.full_name?.message}
        {...register("full_name")}
      />

      <Input
        label="Mobile number (optional)"
        type="tel"
        autoComplete="tel"
        placeholder="+91 98765 43210"
        error={errors.phone_number?.message}
        {...register("phone_number")}
      />

      <Input
        label="Headline"
        placeholder="Final-year CS student building compilers"
        error={errors.headline?.message}
        {...register("headline")}
      />

      <div className="flex flex-col gap-1.5">
        <label htmlFor="basic-about" className="text-sm font-medium text-[var(--slate)]">
          About (optional)
        </label>
        <textarea
          id="basic-about"
          rows={4}
          placeholder="What you build, what you're good at, and what you're looking for."
          className="w-full rounded border border-[var(--rule)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] outline-none transition focus:border-[var(--rule)] "
          {...register("about")}
        />
        {/* Says why it is worth filling despite being optional and scoring
            nothing — otherwise "optional" reads as "ignored". */}
        <p className="text-xs text-[var(--slate)]">
          Doesn&apos;t affect your profile strength, but it is read when matching you to roles.
        </p>
        {errors.about?.message ? (
          <p className="text-xs text-rejected">{errors.about.message}</p>
        ) : null}
      </div>

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
      </div>

      {/* Outside the two-column grid: eleven chips need the full width, and a
          chip field beside a select reads as one control with two behaviours. */}
      <Controller
        control={control}
        name="target_roles"
        render={({ field }) => (
          <TargetRolesField
            value={field.value ?? []}
            onChange={field.onChange}
            error={errors.target_roles?.message}
          />
        )}
      />
    </SectionShell>
  );
}
