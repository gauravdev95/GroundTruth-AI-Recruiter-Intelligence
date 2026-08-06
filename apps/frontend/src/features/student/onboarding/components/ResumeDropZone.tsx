import { FileText, Loader2, RotateCcw, Upload, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { DURATION, EASE, useReducedMotionSafe } from "@/design/motion";
import { Reveal, Shake } from "@/design/primitives";
import { Surface } from "@/design/Surface";

/**
 * The resume drop zone, and the read-in-progress state that follows it.
 *
 * THE PROGRESS STAGES ARE REAL, WITH ONE HONEST EXCEPTION
 *
 * Upload percentage comes from `XMLHttpRequest.upload.onprogress` — a genuine
 * byte count, not a simulation. Once the bytes are delivered the client
 * cannot observe the worker's internals, so the parse stage shows an
 * indeterminate state with a caption describing what the pipeline is doing,
 * NOT a bar that keeps filling. A bar that continues past the last real
 * measurement is the exact dishonesty this product's loading states refuse.
 *
 * The captions ("Reading the document", "Finding sections"…) are ordered to
 * match the actual pipeline stages in
 * `backend/src/domains/resume/extraction/pipeline.py`, so they describe real
 * work even though the client cannot time each one. They advance on a slow
 * loop purely as an indeterminate indicator — which is why none of them
 * carries a tick or a percentage. They say "this is what happens", not "this
 * part is done".
 *
 * WHY THE WHOLE THING USUALLY FINISHES IN UNDER A SECOND
 *
 * Most resumes never reach an LLM. The deterministic pass runs in single-digit
 * milliseconds, so this screen is often gone before the second caption. That
 * is a feature of the architecture, not a reason to add an artificial delay
 * to let the animation "land" — holding a finished result on screen to look
 * more impressive is the same lie in a friendlier costume.
 */

const ACCEPT = ".pdf,.docx";
const MAX_BYTES = 10 * 1024 * 1024;

/** Ordered to match the backend pipeline stages. See the module docstring. */
const PARSE_CAPTIONS = [
  "Reading the document",
  "Finding sections",
  "Reading education and experience",
  "Detecting skills",
  "Scoring what we found",
];

type Phase = "idle" | "uploading" | "parsing" | "failed";

interface ResumeDropZoneProps {
  onUpload: (file: File, onProgress: (percent: number) => void) => Promise<void>;
  /** Student-facing message from the backend's typed parse errors. */
  error?: string | null;
  onRetry?: () => void;
}

function validate(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
    // Names the fix, not just the fault — a `.doc` user needs to be told to
    // re-save, which "invalid file type" does not tell them.
    return name.endsWith(".doc")
      ? "Legacy .doc files aren't supported. Open it and save as PDF or DOCX."
      : "Upload a PDF or DOCX file.";
  }
  if (file.size > MAX_BYTES) {
    return `That file is ${(file.size / 1024 / 1024).toFixed(1)}MB. The limit is 10MB.`;
  }
  if (file.size === 0) return "That file is empty.";
  return null;
}

export function ResumeDropZone({ onUpload, error, onRetry }: ResumeDropZoneProps) {
  const reduced = useReducedMotionSafe();
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [percent, setPercent] = useState(0);
  const [fileName, setFileName] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isDragging, setDragging] = useState(false);
  const [caption, setCaption] = useState(0);

  const message = error ?? localError;

  const start = useCallback(
    async (file: File) => {
      const invalid = validate(file);
      if (invalid) {
        setLocalError(invalid);
        setPhase("failed");
        return;
      }

      setLocalError(null);
      setFileName(file.name);
      setPercent(0);
      setPhase("uploading");

      try {
        await onUpload(file, (value) => {
          setPercent(value);
          // The transition to the indeterminate parse state happens when the
          // last byte lands, which is the last thing the client can actually
          // measure.
          if (value >= 100) setPhase("parsing");
        });
        setPhase("parsing");
      } catch {
        // The thrown error's message is surfaced by the parent via `error`;
        // this only moves the phase so the retry affordance appears.
        setPhase("failed");
      }
    },
    [onUpload],
  );

  // Caption cycling for the indeterminate parse state. Deliberately a plain
  // interval rather than the shared rAF loop: it advances every 900ms, so
  // frame-accurate timing buys nothing and a per-frame callback for a
  // five-step text swap is waste.
  const captionTimer = useRef<number | null>(null);
  if (phase === "parsing" && captionTimer.current === null && !reduced) {
    captionTimer.current = window.setInterval(() => {
      setCaption((current) => (current + 1) % PARSE_CAPTIONS.length);
    }, 900);
  }
  if (phase !== "parsing" && captionTimer.current !== null) {
    window.clearInterval(captionTimer.current);
    captionTimer.current = null;
  }

  if (phase === "uploading" || phase === "parsing") {
    const isUploading = phase === "uploading";
    return (
      <Surface elevation="raised" className="p-6">
        <div className="flex items-center gap-3.5">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--r-md)] bg-[var(--violet)]/12">
            <Loader2 size={17} className="animate-spin text-[var(--violet)]" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-[var(--ink)]">
              {fileName ?? "Your resume"}
            </p>
            <p className="mt-0.5 text-xs text-[var(--slate)]" aria-live="polite">
              {isUploading ? "Uploading" : PARSE_CAPTIONS[caption]}
            </p>
          </div>
          {/* A percentage is shown ONLY while it is measured. */}
          {isUploading ? (
            <span className="machine tabular text-xs text-[var(--muted)]">{percent}%</span>
          ) : null}
        </div>

        <div className="mt-4 h-[3px] overflow-hidden rounded-full bg-[var(--rule)]">
          {isUploading ? (
            <div
              className="h-full origin-left rounded-full"
              style={{
                width: "100%",
                transform: `scaleX(${percent / 100})`,
                background: "linear-gradient(90deg, var(--violet), var(--blue))",
                transition: reduced
                  ? "none"
                  : `transform ${DURATION.fast}s cubic-bezier(${EASE.standard.join(",")})`,
              }}
            />
          ) : (
            // Indeterminate: a travelling sliver, not a filling bar. It
            // communicates "working" without claiming a position.
            <div
              className="h-full w-1/3 rounded-full"
              style={{
                background: "linear-gradient(90deg, transparent, var(--violet), transparent)",
                animation: reduced ? "none" : "gt-indeterminate 1.4s ease-in-out infinite",
              }}
            />
          )}
        </div>

        <style>{`@keyframes gt-indeterminate {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(300%); }
        }`}</style>
      </Surface>
    );
  }

  if (phase === "failed" || message) {
    return (
      <Shake active>
        <Surface elevation="raised" className="border-[var(--failed)]/30 p-6">
          <div className="flex items-start gap-3.5">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--r-md)] bg-[var(--failed)]/12">
              <X size={17} className="text-[var(--failed)]" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[var(--ink)]">We could not read that file</p>
              <p className="mt-1 text-[13px] leading-relaxed text-[var(--slate)]">{message}</p>
            </div>
          </div>

          {/* Every error offers the next action. Two here, because the second
              one is always available even when the first keeps failing. */}
          <div className="mt-5 flex flex-wrap gap-2.5">
            <button
              type="button"
              onClick={() => {
                setPhase("idle");
                setLocalError(null);
                onRetry?.();
              }}
              className="inline-flex items-center gap-1.5 rounded-[var(--r-full)] border border-[var(--rule)] px-4 py-2 text-[13px] font-medium text-[var(--ink)] transition-colors hover:border-[var(--violet)]"
            >
              <RotateCcw size={13} aria-hidden="true" /> Try another file
            </button>
          </div>
        </Surface>
      </Shake>
    );
  }

  return (
    <Reveal trigger="mount">
      <label
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = event.dataTransfer.files?.[0];
          if (file) void start(file);
        }}
        className={[
          "flex cursor-pointer flex-col items-center rounded-[var(--r-lg)] border border-dashed px-6 py-12 text-center backdrop-blur-sm",
          isDragging
            ? "border-[var(--violet)] bg-[var(--violet)]/[0.06]"
            : "border-[var(--rule)] bg-[var(--panel)] hover:border-[var(--violet)]/50",
        ].join(" ")}
        style={
          reduced
            ? undefined
            : {
                transition: `border-color ${DURATION.fast}s ease, background-color ${DURATION.fast}s ease, transform ${DURATION.fast}s cubic-bezier(${EASE.standard.join(",")})`,
                transform: isDragging ? "scale(1.01)" : "scale(1)",
              }
        }
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void start(file);
            // Reset so re-selecting the same file after an error still fires.
            event.target.value = "";
          }}
        />

        <span className="grid h-12 w-12 place-items-center rounded-full bg-[var(--violet)]/10">
          {isDragging ? (
            <FileText size={20} className="text-[var(--violet)]" aria-hidden="true" />
          ) : (
            <Upload size={20} className="text-[var(--violet)]" aria-hidden="true" />
          )}
        </span>

        <p className="mt-4 text-sm font-medium text-[var(--ink)]">
          {isDragging ? "Drop it here" : "Drop your resume, or browse"}
        </p>
        <p className="machine mt-1.5 text-[11px] text-[var(--muted)]">PDF or DOCX · up to 10MB</p>

        <p className="mt-5 max-w-[38ch] text-xs leading-relaxed text-[var(--slate)]">
          We read it and show you what we found. Nothing is saved to your profile until you
          confirm it.
        </p>
      </label>
    </Reveal>
  );
}
