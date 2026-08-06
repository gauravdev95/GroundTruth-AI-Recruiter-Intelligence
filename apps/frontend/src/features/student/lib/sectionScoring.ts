import type { ProfileCompleteness, SectionCacheKey, SectionKey, SectionStatus } from "../api/profileApi";

/**
 * Which scored sections each *form* covers.
 *
 * These two vocabularies stopped being one-to-one when onboarding split GitHub
 * and coding profiles into separate stages. The server scores six sections;
 * the profile editor still renders five forms, because `GET/PUT
 * /sections/technical` remains one resource writing both halves. Only
 * `technical` maps to more than one key — every other row is the identity, and
 * is listed anyway so the map is exhaustive and a new section cannot be added
 * without deciding which form owns it.
 */
export const FORM_SECTION_KEYS: Record<SectionCacheKey, SectionKey[]> = {
  basic: ["basic"],
  technical: ["github", "coding"],
  projects: ["projects"],
  certificates: ["certificates"],
  experience: ["experience"],
};

/**
 * Collapse the scored sections behind one form into the single status its
 * badge and points row render.
 *
 * The aggregation rules follow what each field actually means, rather than
 * summing everything:
 *
 * * **`is_mandatory` is `some`, not `every`.** A form containing one required
 *   section is a required form — GitHub being mandatory is what makes the
 *   technical form mandatory, even though coding profiles beside it are not.
 * * **`is_complete` is `every`.** A form is done when nothing it covers is
 *   still owed. An optional section is always complete, so this reduces to
 *   "the mandatory parts are satisfied".
 * * **`verification` takes the worst actionable state**, matching the
 *   server-side rollup in `completeness.py::_rollup_verification`: pending
 *   first, then rejected, then flagged. A form showing "verified" while half
 *   of it is still being checked would be the exact conflation this codebase
 *   keeps `saved` and `verified` apart to prevent.
 *
 * Returns `undefined` when completeness has not loaded, so callers render
 * nothing rather than a zeroed row that reads as a real score.
 */
export function formSectionStatus(
  completeness: ProfileCompleteness | undefined,
  form: SectionCacheKey,
): SectionStatus | undefined {
  if (!completeness) return undefined;

  const parts = completeness.sections.filter((section) =>
    FORM_SECTION_KEYS[form].includes(section.key),
  );
  if (parts.length === 0) return undefined;
  if (parts.length === 1) return parts[0];

  return {
    // The form's own key, not one of its parts': this status is rendered
    // against a form, and handing back `github` here would make a caller
    // keying on it silently address the wrong row.
    key: form as SectionKey,
    is_complete: parts.every((part) => part.is_complete),
    is_filled: parts.some((part) => part.is_filled),
    is_mandatory: parts.some((part) => part.is_mandatory),
    filled_count: parts.reduce((total, part) => total + part.filled_count, 0),
    required_count: parts.reduce((total, part) => total + part.required_count, 0),
    points_earned: parts.reduce((total, part) => total + part.points_earned, 0),
    points_possible: parts.reduce((total, part) => total + part.points_possible, 0),
    verification: rollupVerification(parts),
    missing: parts.flatMap((part) => part.missing),
  };
}

function rollupVerification(parts: SectionStatus[]): SectionStatus["verification"] {
  const statuses = parts.map((part) => part.verification).filter((status) => status !== null);
  if (statuses.length === 0) return null;
  if (statuses.includes("pending")) return "pending";
  if (statuses.includes("rejected")) return "rejected";
  if (statuses.includes("flagged")) return "flagged";
  return statuses.every((status) => status === "verified") ? "verified" : "unverified";
}
