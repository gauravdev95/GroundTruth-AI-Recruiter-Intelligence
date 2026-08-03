import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { useUploadResume } from "../../resume/hooks/useResumeImport";

/**
 * Holds one in-flight upload across a route change.
 *
 * The entry screen starts the upload and immediately navigates to
 * `/student/profile/setup/resume`, which unmounts it. A mutation living in the
 * page would be torn down mid-transfer and the progress bar would restart from
 * nothing on the next screen, so the state lives on the layout instead — one
 * level above both routes.
 *
 * It holds *only* the transfer. Once the server has the file, the flow's state
 * is the `resume` block of `setup-state` and the job row, both of which survive
 * a refresh; this context deliberately does not, because a transfer that was
 * interrupted by a reload genuinely did not happen.
 */

interface SetupUploadState {
  /** 0-100 while transferring, null when no transfer is in flight. */
  progress: number | null;
  isUploading: boolean;
  error: unknown;
  /** Set from the 202 response. Lets the resume screen start polling without
   * waiting for `setup-state` to refetch. */
  uploadId: string | null;
  jobId: string | null;
  fileName: string | null;
  start: (file: File) => void;
  reset: () => void;
}

const SetupUploadContext = createContext<SetupUploadState | null>(null);

export function SetupUploadProvider({ children }: { children: ReactNode }) {
  const upload = useUploadResume();
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const reset = useCallback(() => {
    setProgress(null);
    setUploadId(null);
    setJobId(null);
    setFileName(null);
    upload.reset();
  }, [upload]);

  const start = useCallback(
    (file: File) => {
      setFileName(file.name);
      setProgress(0);
      setUploadId(null);
      setJobId(null);
      upload.mutate(
        { file, onProgress: setProgress },
        {
          onSuccess: (accepted) => {
            setUploadId(accepted.upload.id);
            setJobId(accepted.async_job_id);
            // Cleared on success so the UI switches from the determinate
            // transfer bar to the indeterminate "Analyzing…" state. Parsing has
            // no measurable total, and leaving a bar at 100% would imply the
            // work was done.
            setProgress(null);
          },
          onError: () => setProgress(null),
        },
      );
    },
    [upload],
  );

  const value = useMemo<SetupUploadState>(
    () => ({
      progress,
      isUploading: upload.isPending,
      error: upload.error,
      uploadId,
      jobId,
      fileName,
      start,
      reset,
    }),
    [progress, upload.isPending, upload.error, uploadId, jobId, fileName, start, reset],
  );

  return <SetupUploadContext.Provider value={value}>{children}</SetupUploadContext.Provider>;
}

export function useSetupUpload(): SetupUploadState {
  const context = useContext(SetupUploadContext);
  if (context === null) {
    throw new Error("useSetupUpload must be used inside <SetupUploadProvider>");
  }
  return context;
}
