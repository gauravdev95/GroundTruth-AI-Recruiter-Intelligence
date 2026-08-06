import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2, Upload, User } from "lucide-react";
import { useRef, useState } from "react";

import { Button, useToast } from "@/components";
import { queryKeys } from "@/lib/queryKeys";

import { profileApi } from "../api/profileApi";
import { getProfileErrorMessage } from "../lib/getProfileErrorMessage";

/** Mirrors `backend/src/domains/student/profile_photos.py`. Checked here so an
 * oversized file fails instantly instead of after an upload, and re-checked
 * there because the client is never trusted. */
const MAX_BYTES = 2 * 1024 * 1024;
const ACCEPTED = ["image/png", "image/jpeg"];

/**
 * The optional profile photo on stage 1.
 *
 * **It lives outside the section form and saves on its own.** Every other
 * field on this stage is part of one JSON body that the student submits with
 * "Save & Next"; a file is not, and folding a multipart upload into that
 * request would make one endpoint responsible for both a document store and a
 * field save. Uploading immediately also means a failed photo costs a retry on
 * the photo rather than the whole stage.
 *
 * **It earns no completeness points, and the copy does not imply otherwise.**
 * A photo is how a recruiter sees a person; nothing about a face is evidence
 * of anything, so scoring it would pay profile strength for a claim the
 * platform cannot check.
 */
export function ProfilePhotoField({ hasPhoto }: { hasPhoto: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [localError, setLocalError] = useState<string | null>(null);

  const photo = useQuery({
    queryKey: ["student", "profile", "photo"],
    queryFn: profileApi.profilePhoto,
    // Only fetch when there is something to fetch — the endpoint answers with
    // nulls rather than 404ing, so an unconditional query would be a request
    // per mount for every student who has no photo.
    enabled: hasPhoto,
  });

  function onSettled() {
    void queryClient.invalidateQueries({ queryKey: ["student", "profile", "photo"] });
    queryClient.setQueryData(queryKeys.studentProfile.section("basic"), undefined);
    void queryClient.invalidateQueries({ queryKey: queryKeys.studentProfile.section("basic") });
  }

  const upload = useMutation({
    mutationFn: profileApi.uploadProfilePhoto,
    onSuccess: () => {
      showToast("Photo updated.", "success");
      onSettled();
    },
  });

  const remove = useMutation({
    mutationFn: profileApi.deleteProfilePhoto,
    onSuccess: () => {
      showToast("Photo removed.", "success");
      onSettled();
    },
  });

  function onPick(file: File | undefined) {
    setLocalError(null);
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      setLocalError("Upload a PNG or JPEG image.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setLocalError("Photos must be at most 2 MB.");
      return;
    }
    upload.mutate(file);
  }

  const busy = upload.isPending || remove.isPending;
  const error =
    localError ??
    (upload.isError ? getProfileErrorMessage(upload.error, "Could not upload that photo.") : null) ??
    (remove.isError ? getProfileErrorMessage(remove.error, "Could not remove the photo.") : null);

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-slate-700">Profile photo (optional)</span>

      <div className="flex items-center gap-4">
        <span className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-full border border-rule bg-panel">
          {photo.data?.url ? (
            // Square-cropped by `object-cover` on a round frame — the spec's
            // "cropped to square" without shipping a crop editor for a
            // 64px avatar.
            <img src={photo.data.url} alt="Your profile photo" className="size-full object-cover" />
          ) : (
            <User size={22} className="text-slate-400" aria-hidden="true" />
          )}
        </span>

        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED.join(",")}
            className="sr-only"
            onChange={(event) => {
              onPick(event.target.files?.[0]);
              // Cleared so re-picking the same file after an error still
              // fires `change`.
              event.target.value = "";
            }}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {upload.isPending ? (
              <Loader2 size={14} className="mr-1.5 animate-spin" aria-hidden="true" />
            ) : (
              <Upload size={14} className="mr-1.5" aria-hidden="true" />
            )}
            {hasPhoto ? "Replace" : "Upload"}
          </Button>

          {hasPhoto ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => remove.mutate()}
            >
              <Trash2 size={14} className="mr-1.5" aria-hidden="true" />
              Remove
            </Button>
          ) : null}
        </div>
      </div>

      <p className="text-xs text-slate-500">
        PNG or JPEG, up to 2 MB. Doesn&apos;t affect your profile strength — it&apos;s how
        recruiters see you, not something we verify.
      </p>

      {error ? (
        <p role="alert" className="text-xs text-rejected">
          {error}
        </p>
      ) : null}
    </div>
  );
}
