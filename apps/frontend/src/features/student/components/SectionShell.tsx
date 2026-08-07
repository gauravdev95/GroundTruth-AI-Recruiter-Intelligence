import { ArrowLeft } from "lucide-react";
import type { FormEventHandler, ReactNode } from "react";

import { Button } from "@/components";

import type { SectionStatus } from "../api/profileApi";
import type { SectionMeta } from "../constants";
import { SectionBadges } from "./SectionBadges";

/** Wizard navigation, supplied only by the onboarding flow.
 *
 * The standalone profile builder passes nothing and keeps its plain "Save
 * section" button: there is no next step there, and a wizard footer on a page
 * you reached from a sidebar would promise a sequence that does not exist. */
export interface SectionNav {
  /** Called after a successful save, to advance. The form owns the save; the
   * wizard owns where "next" goes. */
  onSaved: () => void;
  /** Absent on the first step of the wizard. */
  onPrevious?: () => void;
}

interface SectionShellProps {
  meta: SectionMeta;
  status: SectionStatus | undefined;
  onSubmit: FormEventHandler<HTMLFormElement>;
  isSaving: boolean;
  errorMessage: string | null;
  children: ReactNode;
  nav?: SectionNav;
}

/**
 * Shared chrome for all five section forms: heading, badges, error surface and
 * the save control.
 *
 * Saving is per section and explicit ("autosave on submit"), never on blur —
 * a half-typed GitHub username must not reach the server and queue a
 * verification job for a URL the student is still editing.
 *
 * In the onboarding wizard the same submit both saves *and* advances, which is
 * why `nav.onSaved` is threaded down to the form rather than the wizard
 * watching for a mutation to settle: only the form knows whether validation
 * passed, and a wizard that advanced on anything less would skip a step whose
 * fields never reached the server.
 */
export function SectionShell({
  meta,
  status,
  onSubmit,
  isSaving,
  errorMessage,
  children,
  nav,
}: SectionShellProps) {
  return (
    <form onSubmit={onSubmit} noValidate className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-6">
      <header className="mb-5 border-b border-[var(--rule)] pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-lg font-semibold text-[var(--ink)]">
            {meta.title}
            {meta.isMandatory ? (
              <span className="ml-2 align-middle text-xs font-normal text-[var(--flagged)]">Required</span>
            ) : (
              <span className="ml-2 align-middle text-xs font-normal text-[var(--muted)]">Optional</span>
            )}
          </h2>
          {status ? <SectionBadges section={status} /> : null}
        </div>
        <p className="mt-1 text-sm text-[var(--slate)]">{meta.description}</p>
      </header>

      {errorMessage ? (
        <p role="alert" className="mb-4 rounded border border-[var(--failed)]/30 bg-[var(--failed)]/10 px-3 py-2 text-sm text-[var(--failed)]">
          {errorMessage}
        </p>
      ) : null}

      <div className="space-y-5">{children}</div>

      <footer className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--rule)] pt-4">
        {nav?.onPrevious ? (
          <Button type="button" variant="secondary" onClick={nav.onPrevious} disabled={isSaving}>
            <ArrowLeft size={16} aria-hidden="true" className="mr-1.5" />
            Previous
          </Button>
        ) : (
          // Keeps "Save" hard right whether or not there is a Previous button,
          // instead of letting it slide left on the first step.
          <span aria-hidden="true" />
        )}

        <Button type="submit" isLoading={isSaving} disabled={isSaving}>
          {isSaving ? "Saving..." : nav ? "Save & Next" : "Save section"}
        </Button>
      </footer>
    </form>
  );
}
