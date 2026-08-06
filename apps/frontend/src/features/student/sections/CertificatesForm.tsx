import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { Button, Input, useToast } from "@/components";

import type { CertificatesSection, SectionStatus } from "../api/profileApi";
import { VerificationBadge } from "../components/SectionBadges";
import { SectionShell, type SectionNav } from "../components/SectionShell";
import { CertificateFileField } from "./CertificateFileField";
import { SECTIONS } from "../constants";
import { useSaveCertificates } from "../hooks/useProfileSection";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";
import {
  certificatesSchema,
  type CertificatesForm as CertificatesFormValues,
} from "../schemas/profileSchemas";

const META = SECTIONS[3];

interface CertificatesFormProps {
  data: CertificatesSection;
  status: SectionStatus | undefined;
  nav?: SectionNav;
}

function toDefaults(data: CertificatesSection): CertificatesFormValues {
  return {
    certificates: data.certificates.map((certificate) => ({
      title: certificate.title,
      issuer: certificate.issuer,
      issued_at: certificate.issued_at,
      credential_url: certificate.credential_url,
      // The name only — the server never returns the object key, so an
      // untouched certificate re-saves without one and the attachment is
      // preserved server-side. See `CertificateItem.remove_file`.
      existing_file_name: certificate.file_name ?? undefined,
      remove_file: false,
    })),
  } as CertificatesFormValues;
}

export function CertificatesForm({ data, status, nav }: CertificatesFormProps) {
  const save = useSaveCertificates();
  const { showToast } = useToast();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<CertificatesFormValues>({
    resolver: zodResolver(certificatesSchema),
    defaultValues: toDefaults(data),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "certificates" });

  useEffect(() => {
    reset(toDefaults(data));
  }, [data, reset]);

  const onSubmit = handleSubmit((values) => {
    save.mutate(
      {
        certificates: values.certificates.map((certificate) => ({
          title: certificate.title,
          issuer: certificate.issuer,
          issued_at: certificate.issued_at,
          credential_url: certificate.credential_url,
          // Sent only for a file uploaded in this session. `existing_file_name`
          // is client-only bookkeeping and would be a 422 on the server, which
          // forbids unknown keys.
          file_object_key: certificate.file_object_key,
          file_name: certificate.file_object_key ? certificate.file_name : undefined,
          file_content_type: certificate.file_content_type,
          file_size_bytes: certificate.file_size_bytes,
          remove_file: certificate.remove_file || undefined,
        })),
      },
      {
        onSuccess: () => {
          showToast("Certificates saved.", "success");
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
      {fields.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule bg-panel px-4 py-6 text-center text-sm text-slate-500">
          No certificates yet.
        </p>
      ) : null}

      {fields.map((field, index) => {
        const existing = data.certificates[index];

        return (
          <div key={field.id} className="rounded-xl border border-rule bg-panel p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className="font-mono text-xs text-slate-500">Certificate {index + 1}</span>
              <div className="flex items-center gap-2">
                {existing ? <VerificationBadge status={existing.verification_status} /> : null}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => remove(index)}
                  aria-label={`Remove certificate ${index + 1}`}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </Button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="Title"
                  placeholder="AWS Solutions Architect Associate"
                  error={errors.certificates?.[index]?.title?.message}
                  {...register(`certificates.${index}.title` as const)}
                />
                <Input
                  label="Issuer"
                  placeholder="Amazon Web Services"
                  error={errors.certificates?.[index]?.issuer?.message}
                  {...register(`certificates.${index}.issuer` as const)}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  type="date"
                  label="Issued on (optional)"
                  error={errors.certificates?.[index]?.issued_at?.message}
                  {...register(`certificates.${index}.issued_at` as const)}
                />
                <Input
                  label="Credential URL (optional)"
                  placeholder="https://credly.com/badges/..."
                  error={errors.certificates?.[index]?.credential_url?.message}
                  {...register(`certificates.${index}.credential_url` as const)}
                />
              </div>

              <CertificateFileField
                pending={
                  watch(`certificates.${index}.file_object_key`)
                    ? {
                        file_object_key: watch(`certificates.${index}.file_object_key`) as string,
                        file_name: watch(`certificates.${index}.file_name`) as string,
                        file_content_type: watch(
                          `certificates.${index}.file_content_type`,
                        ) as string,
                        file_size_bytes: watch(`certificates.${index}.file_size_bytes`) as number,
                      }
                    : null
                }
                existingFileName={watch(`certificates.${index}.existing_file_name`) ?? null}
                markedForRemoval={watch(`certificates.${index}.remove_file`) === true}
                onUploaded={(upload) => {
                  setValue(`certificates.${index}.file_object_key`, upload.file_object_key);
                  setValue(`certificates.${index}.file_name`, upload.file_name);
                  setValue(`certificates.${index}.file_content_type`, upload.file_content_type);
                  setValue(`certificates.${index}.file_size_bytes`, upload.file_size_bytes);
                  // A fresh upload supersedes a pending removal — the two
                  // together are rejected by the server as contradictory.
                  setValue(`certificates.${index}.remove_file`, false);
                }}
                onRemove={() => {
                  setValue(`certificates.${index}.file_object_key`, undefined);
                  setValue(`certificates.${index}.file_name`, undefined);
                  setValue(`certificates.${index}.file_content_type`, undefined);
                  setValue(`certificates.${index}.file_size_bytes`, undefined);
                  // Only meaningful for a file that is already stored. Setting
                  // it for a just-uploaded one is harmless: the key is gone, so
                  // there is nothing left to detach.
                  setValue(`certificates.${index}.remove_file`, true);
                }}
              />
            </div>
          </div>
        );
      })}

      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() =>
          append({ title: "", issuer: "", issued_at: null, credential_url: null, remove_file: false })
        }
      >
        <Plus size={14} aria-hidden="true" /> Add certificate
      </Button>

      <p className="rounded-xl border border-rule bg-panel px-3 py-2 text-xs text-slate-500">
        Certificates with a credential URL are queued for checking. Without a URL there is nothing to
        check, so the entry is recorded as your own claim.
      </p>
    </SectionShell>
  );
}
