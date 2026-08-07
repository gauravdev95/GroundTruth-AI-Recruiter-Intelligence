import { useMutation } from "@tanstack/react-query";
import { FileText, Paperclip, Trash2 } from "lucide-react";
import { useRef } from "react";

import { Button, useToast } from "@/components";

import { profileApi, type CertificateUpload } from "../api/profileApi";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";

/** Mirrors `certificate_files.MAX_BYTES` / `_MAGIC_PREFIXES`. Checked here so
 * an oversized file is refused before it is uploaded rather than after; the
 * server sniffs the bytes and re-checks the size regardless. */
const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPT = "application/pdf,image/png,image/jpeg";

interface CertificateFileFieldProps {
  /** Uploaded during *this* editing session. */
  pending: CertificateUpload | null;
  /** Already attached server-side. The object key is never returned, so this
   * is all the client knows about it — which is why removal is an explicit
   * flag rather than "send no key". */
  existingFileName: string | null;
  markedForRemoval: boolean;
  onUploaded: (upload: CertificateUpload) => void;
  onRemove: () => void;
}

export function CertificateFileField({
  pending,
  existingFileName,
  markedForRemoval,
  onUploaded,
  onRemove,
}: CertificateFileFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  const upload = useMutation({
    mutationFn: profileApi.uploadCertificateFile,
    onSuccess: (result) => {
      onUploaded(result);
      showToast("Certificate uploaded.", "success");
    },
    onError: (error) => showToast(getProfileErrorMessage(error), "error"),
  });

  const attachedName = pending?.file_name ?? (markedForRemoval ? null : existingFileName);

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-[var(--slate)]">Certificate file (optional)</span>

      {attachedName ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--rule)] bg-[var(--panel)] px-3 py-2">
          <FileText size={15} aria-hidden="true" className="text-[var(--slate)]" />
          <span className="min-w-0 flex-1 truncate text-sm text-[var(--slate)]">{attachedName}</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRemove}
            aria-label={`Remove ${attachedName}`}
          >
            <Trash2 size={15} aria-hidden="true" />
          </Button>
        </div>
      ) : (
        <div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Cleared immediately so picking the *same* file again after a
              // failed upload still fires `change` — the input keeps its value
              // otherwise and the second attempt silently does nothing.
              event.target.value = "";
              if (!file) return;
              if (file.size > MAX_BYTES) {
                showToast("Certificates must be at most 5 MB.", "error");
                return;
              }
              upload.mutate(file);
            }}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            isLoading={upload.isPending}
            onClick={() => inputRef.current?.click()}
          >
            <Paperclip size={14} aria-hidden="true" className="mr-1.5" />
            Upload certificate
          </Button>
          <p className="mt-1 text-xs text-[var(--slate)]">PDF, PNG or JPEG, up to 5 MB.</p>
        </div>
      )}
    </div>
  );
}
