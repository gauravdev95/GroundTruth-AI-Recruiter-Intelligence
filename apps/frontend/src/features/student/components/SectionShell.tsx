import type { FormEventHandler, ReactNode } from "react";

import { Button } from "@/components";

import type { SectionStatus } from "../api/profileApi";
import type { SectionMeta } from "../constants";
import { SectionBadges } from "./SectionBadges";

interface SectionShellProps {
  meta: SectionMeta;
  status: SectionStatus | undefined;
  onSubmit: FormEventHandler<HTMLFormElement>;
  isSaving: boolean;
  errorMessage: string | null;
  children: ReactNode;
}

/**
 * Shared chrome for all five section forms: heading, badges, error surface and
 * the save control.
 *
 * Saving is per section and explicit ("autosave on submit"), never on blur —
 * a half-typed GitHub username must not reach the server and queue a
 * verification job for a URL the student is still editing.
 */
export function SectionShell({
  meta,
  status,
  onSubmit,
  isSaving,
  errorMessage,
  children,
}: SectionShellProps) {
  return (
    <form onSubmit={onSubmit} noValidate className="rounded-2xl border border-rule bg-white p-6">
      <header className="mb-5 border-b border-rule pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-lg font-semibold text-ink">
            {meta.title}
            {meta.isMandatory ? (
              <span className="ml-2 align-middle text-xs font-normal text-flagged">Required</span>
            ) : (
              <span className="ml-2 align-middle text-xs font-normal text-slate-400">Optional</span>
            )}
          </h2>
          {status ? <SectionBadges section={status} /> : null}
        </div>
        <p className="mt-1 text-sm text-slate-500">{meta.description}</p>
      </header>

      {errorMessage ? (
        <p role="alert" className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {errorMessage}
        </p>
      ) : null}

      <div className="space-y-5">{children}</div>

      <footer className="mt-6 flex items-center justify-end gap-3 border-t border-rule pt-4">
        <Button type="submit" isLoading={isSaving} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save section"}
        </Button>
      </footer>
    </form>
  );
}
