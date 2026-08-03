import { Check, Clock, FileText, PencilLine } from "lucide-react";
import { useRef } from "react";

import { ResumeDropZone, type ResumeDropZoneHandle } from "./ResumeDropZone";

/**
 * The two paths, side by side and equal height.
 *
 * `items-stretch` on the grid plus `h-full` + `flex-col` on each card is what
 * makes the two footers line up when the left card's drop zone makes it taller
 * than the right's panel. `mt-auto` on the footer row pins it to the bottom
 * rather than letting it float under short content.
 *
 * Neither choice is binding — both cards stay reachable from the other path at
 * any point, and picking one saves nothing, so the copy avoids any language
 * suggesting a commitment.
 */

function TickList({ items, tone }: { items: string[]; tone: "violet" | "amber" }) {
  return (
    <ul className="mt-3 space-y-2">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2 text-xs leading-relaxed text-slate-600">
          <Check
            size={14}
            strokeWidth={3}
            aria-hidden="true"
            className={tone === "violet" ? "mt-0.5 shrink-0 text-violet-600" : "mt-0.5 shrink-0 text-amber-600"}
          />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function EstimatedTime({ value }: { value: string }) {
  return (
    <div className="flex shrink-0 items-center gap-2 text-slate-500">
      <Clock size={16} aria-hidden="true" />
      <span className="leading-tight">
        <span className="block text-[10px] uppercase tracking-wide">Estimated Time</span>
        <span className="block text-xs font-semibold text-slate-700">{value}</span>
      </span>
    </div>
  );
}

interface UploadResumeCardProps {
  onFile: (file: File) => void;
  onReject: (reason: string) => void;
  isUploading: boolean;
  error: string | null;
}

export function UploadResumeCard({ onFile, onReject, isUploading, error }: UploadResumeCardProps) {
  // The footer button opens the drop zone's own input rather than owning a
  // second one, so both entry points run the same validation.
  const dropZone = useRef<ResumeDropZoneHandle>(null);

  return (
    <section
      aria-labelledby="setup-option-resume"
      className="relative flex h-full flex-col rounded-2xl border border-violet-100 bg-white p-5 shadow-sm shadow-violet-900/5 sm:p-6"
    >
      <span className="absolute -top-2.5 left-5 rounded-full bg-gradient-to-r from-violet-500 to-indigo-600 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white shadow-sm shadow-violet-500/30">
        Recommended
      </span>

      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600"
        >
          <FileText size={22} strokeWidth={1.75} />
        </span>
        <div className="min-w-0">
          <h3 id="setup-option-resume" className="font-display text-base font-semibold text-slate-900">
            Upload Resume
          </h3>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
            Upload your resume and let our AI extract information automatically.
          </p>
        </div>
      </div>

      <div className="mt-5">
        <ResumeDropZone ref={dropZone} onFile={onFile} onReject={onReject} disabled={isUploading} />
      </div>

      {error ? (
        <p role="alert" className="mt-3 text-xs font-medium text-red-600">
          {error}
        </p>
      ) : null}

      <div className="mt-5 rounded-xl bg-violet-50/70 p-4">
        <h4 className="text-xs font-semibold text-violet-900">AI-Powered Resume Parsing</h4>
        <TickList
          tone="violet"
          items={[
            "Extracts education, skills, experience & more",
            "Saves time and reduces manual work",
            "You can review & edit extracted details",
          ]}
        />
      </div>

      <div className="mt-auto flex items-center gap-4 pt-5">
        <button
          type="button"
          onClick={() => dropZone.current?.open()}
          disabled={isUploading}
          className="flex-1 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-violet-500/30 transition hover:from-violet-700 hover:to-indigo-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isUploading ? "Uploading…" : "Upload Resume"}
        </button>
        <EstimatedTime value="30 sec" />
      </div>
    </section>
  );
}

export function FillManuallyCard({ onStart }: { onStart: () => void }) {
  return (
    <section
      aria-labelledby="setup-option-manual"
      className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-amber-100 bg-white p-5 shadow-sm shadow-amber-900/5 sm:p-6"
    >
      {/* Decorative only — a soft amber illustration that anchors the card's
          secondary accent without carrying information a screen reader needs. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 120 120"
        className="pointer-events-none absolute -right-4 -top-4 size-32 text-amber-200/70"
      >
        <circle cx="76" cy="34" r="30" fill="currentColor" opacity="0.45" />
        <rect x="30" y="52" width="52" height="7" rx="3.5" fill="currentColor" />
        <rect x="30" y="68" width="38" height="7" rx="3.5" fill="currentColor" opacity="0.7" />
        <rect x="30" y="84" width="46" height="7" rx="3.5" fill="currentColor" opacity="0.45" />
      </svg>

      <div className="relative flex items-start gap-3">
        <span
          aria-hidden="true"
          className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600"
        >
          <PencilLine size={22} strokeWidth={1.75} />
        </span>
        <div className="min-w-0">
          <h3 id="setup-option-manual" className="font-display text-base font-semibold text-slate-900">
            Fill Manually
          </h3>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
            Fill your information manually step by step.
          </p>
        </div>
      </div>

      <div className="relative mt-5 rounded-xl bg-amber-50/80 p-4">
        <h4 className="text-xs font-semibold text-amber-900">Why fill manually?</h4>
        <TickList
          tone="amber"
          items={[
            "Enter information step by step",
            "Full control over your data",
            "Add details not present in resume",
            "Perfect for freshers & new graduates",
          ]}
        />
      </div>

      <div className="relative mt-auto flex items-center gap-4 pt-5">
        <button
          type="button"
          onClick={onStart}
          className="flex-1 rounded-xl border-2 border-amber-400 bg-white px-4 py-2.5 text-sm font-semibold text-amber-700 transition hover:bg-amber-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500"
        >
          Start Manually
        </button>
        <EstimatedTime value="5–8 min" />
      </div>
    </section>
  );
}
