import { UploadCloud } from "lucide-react";
import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
} from "react";

import { cn } from "@/lib/utils";

import { RESUME_ACCEPT, RESUME_HINT, validateResumeFile } from "../lib/validateResumeFile";

interface ResumeDropZoneProps {
  onFile: (file: File) => void;
  onReject: (reason: string) => void;
  disabled?: boolean;
}

/** Lets the card's "Upload Resume" button open the same picker the zone owns,
 * so there is one file input and one validation path rather than two that can
 * drift. */
export interface ResumeDropZoneHandle {
  open: () => void;
}

/**
 * Drag-and-drop plus click-to-browse over one hidden file input.
 *
 * Built on a `<button>` rather than a styled `<div role="button">` so Enter and
 * Space activate it for free and it lands in the tab order without a
 * `tabIndex` — the keyboard path is the same code path as the mouse one, which
 * is what stops it rotting.
 *
 * Validation here is a fast reject, not a gate: `validateResumeFile` only reads
 * the name and size, and the server re-decides from the file's magic bytes.
 */
export const ResumeDropZone = forwardRef<ResumeDropZoneHandle, ResumeDropZoneProps>(
  function ResumeDropZone({ onFile, onReject, disabled }, ref) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setDragging] = useState(false);

  useImperativeHandle(ref, () => ({ open: () => inputRef.current?.click() }), []);

  function accept(file: File | undefined) {
    if (!file) return;
    const rejection = validateResumeFile(file);
    if (rejection) {
      onReject(rejection.reason);
      return;
    }
    onFile(file);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    accept(event.dataTransfer.files?.[0]);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    // A native <button> already fires click on Enter and Space; this only stops
    // Space from scrolling the page before it does.
    if (event.key === " ") event.preventDefault();
  }

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onKeyDown={handleKeyDown}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        aria-label={`Upload your resume. ${RESUME_HINT}. Drag and drop a file here, or activate to browse.`}
        className={cn(
          "flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500",
          disabled && "cursor-not-allowed opacity-60",
          isDragging
            ? "border-violet-500 bg-violet-50"
            : "border-violet-200 bg-violet-50/40 hover:border-violet-400 hover:bg-violet-50",
        )}
      >
        <UploadCloud
          size={30}
          strokeWidth={1.5}
          className={cn("transition", isDragging ? "text-violet-600" : "text-violet-400")}
          aria-hidden="true"
        />
        <span className="mt-3 block text-sm font-semibold text-slate-800">
          Drag &amp; drop your resume here
        </span>
        <span className="mt-0.5 block text-xs text-slate-500">or click to browse</span>
        <span className="mt-3 block text-[11px] font-medium text-slate-400">{RESUME_HINT}</span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept={RESUME_ACCEPT}
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          accept(event.target.files?.[0]);
          // Cleared so re-selecting the same file after a rejection still fires
          // `change` — the browser suppresses it for an unchanged value.
          event.target.value = "";
        }}
      />
    </>
  );
  },
);
