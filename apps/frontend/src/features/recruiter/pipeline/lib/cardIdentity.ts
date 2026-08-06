/**
 * Initials for a board card's avatar.
 *
 * Taken from the headline, because **the board never receives the candidate's
 * name.** Every recruiter-facing payload in this codebase
 * (`pipeline/service.py::get_pipeline`, `pipeline/evidence.py`) returns
 * `headline` and stops — screening here is evidence-first by construction,
 * and the name arrives only once a conversation is opened on an application.
 *
 * So "AR" on a card is the initials of "Android Rendering Engineer", not of a
 * person. That is a weaker avatar than a name would give, and it is the
 * correct trade: an avatar exists to make a card findable again after you
 * scroll past it, which initials of *anything* stable accomplish, and putting
 * a name on a screening card is how name-based bias gets back into a product
 * built to remove it.
 */
export function initialsFrom(headline: string | null): string {
  const words = (headline ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "··";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}
