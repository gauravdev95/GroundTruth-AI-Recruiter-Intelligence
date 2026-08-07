import { X } from "lucide-react";
import { useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

export interface TagInputProps {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  /** Rendered under the field. Shown in `--flagged` when `error` is set. */
  hint?: string;
  error?: string;
  /** Optional cap. Reaching it disables the text input rather than silently
   * dropping what the recruiter types next. */
  max?: number;
  className?: string;
}

/**
 * Free-tag multi-select — type, press Enter or comma, get a chip.
 *
 * De-duplicates case-insensitively but preserves the *first* casing entered.
 * "PostgreSQL" and "postgresql" are one skill to the matching engine
 * (`domains/matching/scoring.py` casefolds every comparison), so accepting
 * both would show a recruiter two chips that produce one requirement — and
 * lower-casing what they typed to prove it would render their job ad in a
 * casing they did not choose.
 *
 * Backspace on an empty input removes the last chip, which is the behaviour
 * every tag field in every ATS has and the one thing recruiters try first.
 */
export function TagInput({
  label,
  value,
  onChange,
  placeholder,
  hint,
  error,
  max,
  className,
}: TagInputProps) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const id = useId();
  const atCapacity = max !== undefined && value.length >= max;

  const commit = (raw: string) => {
    const tag = raw.trim().replace(/,+$/, "").trim();
    if (!tag || atCapacity) return;
    if (value.some((existing) => existing.toLowerCase() === tag.toLowerCase())) {
      setDraft("");
      return;
    }
    onChange([...value, tag]);
    setDraft("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      // Enter inside a form submits it. A recruiter adding their third skill
      // must not post the job by doing so.
      event.preventDefault();
      commit(draft);
      return;
    }
    if (event.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium text-[var(--slate)]">
        {label}
      </label>

      <div
        className={cn(
          "flex min-h-[42px] w-full flex-wrap items-center gap-1.5 rounded border bg-[var(--panel)] px-2 py-1.5 transition focus-within:ring-2 focus-within:",
          error ? "border-[var(--flagged)] focus-within:border-[var(--flagged)]" : "border-[var(--rule)] focus-within:border-[var(--rule)]",
        )}
        // Clicking the padding of a tag field should focus it — otherwise the
        // hit target is only the last few pixels of the text cursor.
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) {
            event.preventDefault();
            inputRef.current?.focus();
          }
        }}
      >
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full border border-[var(--rule)]/15 bg-[var(--panel)] py-0.5 pl-2.5 pr-1 text-xs font-medium text-[var(--ink)]"
          >
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((t) => t !== tag))}
              aria-label={`Remove ${tag}`}
              className="rounded-full p-0.5 text-[var(--muted)] transition hover:bg-[var(--violet)]/10 hover:text-[var(--ink)]"
            >
              <X size={11} aria-hidden="true" />
            </button>
          </span>
        ))}

        <input
          ref={inputRef}
          id={id}
          value={draft}
          disabled={atCapacity}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          // Committing on blur is what stops a half-typed skill from being
          // silently discarded when the recruiter tabs to the next field.
          onBlur={() => commit(draft)}
          placeholder={atCapacity ? undefined : (placeholder ?? "Type a skill and press Enter")}
          aria-invalid={Boolean(error)}
          aria-describedby={hint || error ? `${id}-hint` : undefined}
          className="min-w-[10rem] flex-1 bg-transparent px-1 py-1 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] outline-none disabled:cursor-not-allowed"
        />
      </div>

      {error || hint ? (
        <p
          id={`${id}-hint`}
          role={error ? "alert" : undefined}
          className={cn("text-xs", error ? "text-[var(--flagged)]" : "text-[var(--slate)]")}
        >
          {error ?? hint}
        </p>
      ) : null}
    </div>
  );
}
