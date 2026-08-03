import { Badge } from "@/components";

import type { SectionStatus, VerificationStatus } from "../api/profileApi";

/**
 * Two independent badges, never one.
 *
 * "Filled" is about whether the student entered anything; "verified" is about
 * whether a Phase II worker has checked it. A section can be fully filled and
 * still entirely unverified, and a rejected claim is still filled. Collapsing
 * these into a single chip would let a student read "saved" as "proven", which
 * is exactly the claim GroundTruth exists to not make.
 *
 * Colours follow the landing page's meaning (see `tailwind.config.ts`):
 * `verified` green is proven by an artefact, `flagged` amber is claimed but
 * unchecked.
 */

const FILL_LABELS = {
  empty: "Empty",
  partial: "In progress",
  saved: "Saved",
} as const;

function fillState(section: SectionStatus): keyof typeof FILL_LABELS {
  if (!section.is_filled) return "empty";
  if (section.is_mandatory && !section.is_complete) return "partial";
  return "saved";
}

export function FilledBadge({ section }: { section: SectionStatus }) {
  const state = fillState(section);
  const variant = state === "empty" ? "neutral" : state === "partial" ? "warning" : "info";

  return (
    <Badge variant={variant} title="Whether you have filled this section in">
      {FILL_LABELS[state]}
    </Badge>
  );
}

const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  unverified: "Not checked",
  pending: "Pending verification",
  verified: "Verified",
  rejected: "Could not verify",
  flagged: "Flagged for review",
};

const VERIFICATION_VARIANTS: Record<VerificationStatus, "neutral" | "warning" | "success" | "danger"> = {
  unverified: "neutral",
  pending: "warning",
  verified: "success",
  rejected: "danger",
  flagged: "warning",
};

export function VerificationBadge({ status }: { status: VerificationStatus | null }) {
  // `null` means the section has nothing verifiable in it — render nothing
  // rather than an "unverified" badge that implies a failed check.
  if (status === null) return null;

  return (
    <Badge
      variant={VERIFICATION_VARIANTS[status]}
      title="Whether GroundTruth has independently checked this section"
    >
      {VERIFICATION_LABELS[status]}
    </Badge>
  );
}

export function SectionBadges({ section }: { section: SectionStatus }) {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <FilledBadge section={section} />
      <VerificationBadge status={section.verification} />
    </span>
  );
}
