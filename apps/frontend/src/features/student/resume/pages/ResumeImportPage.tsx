import { CheckCircle2, FileText, Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Button, ErrorState, Skeleton, useToast } from "@/components";

import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { DraftReview } from "../components/DraftReview";
import {
  useJobStatus,
  useResumeDraft,
  useUploadResume,
} from "../hooks/useResumeImport";

const ACCEPTED = ".pdf,.docx";

/**
 * Resume import: upload → poll → review → confirm.
 *
 * The upload request returns 202 immediately; everything after it is driven by
 * polling the job row, so the page never blocks on parsing or an LLM call.
 */
export function ResumeImportPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const upload = useUploadResume();
  const { showToast } = useToast();
  const job = useJobStatus(jobId);

  const extractionSucceeded = job.data?.status === "succeeded";
  const draft = useResumeDraft(uploadId, extractionSucceeded);

  function handleFile(file: File) {
    // No `onProgress`: this page is the standalone importer, which uploads
    // from a modest form rather than the setup flow's drop zone and has no
    // progress bar to feed.
    upload.mutate({ file }, {
      onSuccess: (accepted) => {
        setUploadId(accepted.upload.id);
        setJobId(accepted.async_job_id);
        showToast("Uploaded. Reading your resume now.", "info");
      },
    });
  }

  function reset() {
    setUploadId(null);
    setJobId(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const isWorking =
    upload.isPending || job.data?.status === "pending" || job.data?.status === "running";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold text-ink">Import from resume</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload a PDF or DOCX. We&apos;ll read it and show you what we found — nothing is saved
          until you confirm it.
        </p>
      </header>

      {!uploadId ? (
        <div className="rounded-2xl border border-dashed border-rule bg-panel p-10 text-center">
          <Upload size={28} className="mx-auto text-slate-400" aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-ink">Choose your resume</p>
          <p className="mt-1 text-xs text-slate-500">PDF or DOCX, up to 10 MB.</p>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
          <Button
            type="button"
            className="mt-4"
            onClick={() => inputRef.current?.click()}
            isLoading={upload.isPending}
            disabled={upload.isPending}
          >
            {upload.isPending ? "Uploading..." : "Select file"}
          </Button>
          {upload.isError ? (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {getProfileErrorMessage(upload.error, "Could not upload that file.")}
            </p>
          ) : null}
        </div>
      ) : null}

      {uploadId && isWorking ? (
        <div className="rounded-2xl border border-rule bg-white p-6" role="status">
          <div className="flex items-center gap-3">
            <Loader2 size={18} className="animate-spin text-ink" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-ink">Reading your resume…</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {job.data && job.data.attempts > 1
                  ? `Retrying (attempt ${job.data.attempts}). This can take a moment.`
                  : "This usually takes a few seconds. You can leave this page open."}
              </p>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </div>
      ) : null}

      {job.data?.status === "failed" ? (
        <ErrorState
          title="We couldn't read that resume"
          description={
            job.data.error?.includes(":")
              ? job.data.error.slice(job.data.error.indexOf(":") + 1).trim()
              : (job.data.error ?? "Something went wrong reading the file.")
          }
          action={
            <Button type="button" variant="secondary" size="sm" onClick={reset}>
              Try another file
            </Button>
          }
        />
      ) : null}

      {extractionSucceeded && draft.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : null}

      {extractionSucceeded && draft.isError ? (
        <ErrorState
          title="Couldn't load the extracted data"
          description="The resume was read, but we couldn't fetch the result."
          action={
            <Button type="button" variant="secondary" size="sm" onClick={() => void draft.refetch()}>
              Try again
            </Button>
          }
        />
      ) : null}

      {extractionSucceeded && draft.data ? (
        draft.data.draft.status === "pending_review" ? (
          <DraftReview detail={draft.data} onDone={reset} />
        ) : (
          <div className="flex items-start gap-3 rounded-2xl border border-verified/30 bg-verified/5 p-4">
            <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-verified" aria-hidden="true" />
            <div className="text-sm">
              <p className="font-medium text-ink">
                {draft.data.draft.status === "confirmed"
                  ? "This resume has been imported."
                  : "This draft was discarded."}
              </p>
              <Button type="button" variant="ghost" size="sm" className="mt-2 -ml-3" onClick={reset}>
                Import another resume
              </Button>
            </div>
          </div>
        )
      ) : null}

      <p className="flex items-start gap-2 text-xs text-slate-500">
        <FileText size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
        Your resume is stored privately and only used to pre-fill this form. Imported accounts and
        links are queued for verification just like ones you type in yourself.
      </p>
    </div>
  );
}
