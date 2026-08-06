/**
 * The skills a recruiter typed on the creation form, held between that screen
 * and the confirmation screen.
 *
 * **Why they are not sent with the job.** `job_postings` has no skills
 * column, and that is deliberate rather than an omission:
 * `domains/recruiter/models.py` routes every skill through
 * `job_requirements`, which only `confirm_job` writes. One path in means a
 * skill on a published job has always been seen and approved by a human —
 * an invariant that a "skills" field on the create endpoint would quietly
 * end, because it would let a typo'd requirement reach the matching index
 * without anyone having read it.
 *
 * So the tags travel client-side and are merged into the *editable* must-have
 * list on the confirmation screen, where they sit alongside the LLM's
 * extraction under the same review and the same Confirm button. The
 * recruiter's intent survives; the invariant does.
 *
 * `sessionStorage` rather than router state alone because the confirmation
 * screen is a URL a recruiter will refresh — extraction takes a few seconds
 * and reloading is what people do while they wait. Session-scoped, so it
 * does not outlive the tab, and cleared on confirm.
 */

const KEY_PREFIX = "gt.recruiter.seed-skills.";

function key(jobId: string): string {
  return `${KEY_PREFIX}${jobId}`;
}

export function saveSeedSkills(jobId: string, skills: string[]): void {
  if (skills.length === 0) return;
  try {
    sessionStorage.setItem(key(jobId), JSON.stringify(skills));
  } catch {
    // Private-browsing quota, or storage disabled entirely. The tags are a
    // convenience layered over an extraction that runs regardless, so losing
    // them costs the recruiter some retyping on the next screen — never the
    // job. Failing loudly here would be worse than that.
  }
}

export function readSeedSkills(jobId: string): string[] {
  try {
    const raw = sessionStorage.getItem(key(jobId));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((s): s is string => typeof s === "string") : [];
  } catch {
    return [];
  }
}

export function clearSeedSkills(jobId: string): void {
  try {
    sessionStorage.removeItem(key(jobId));
  } catch {
    /* see saveSeedSkills */
  }
}
