import { ORIGIN } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";

/**
 * §11 — why we built this.
 *
 * On a pre-launch page this section does the job social proof normally does.
 * There are no users to count, no logos to show and no testimonials that would
 * be true, so what remains is the reason — and a stranger extends trust to a
 * specific reason in a way they never extend it to a generic one. "We kept
 * meeting the same person: two years of real commits and no channel through
 * which any of it was visible" is checkable against the reader's own experience
 * in a way that "we're passionate about fairness in hiring" is not.
 *
 * First person plural, three short paragraphs, and no adjectives about the
 * team. Every figure in it already appeared in §01, so this section asserts
 * nothing new — it explains what the page has already shown.
 */
export function Origin() {
  return (
    <section className="sec" id="origin">
      <div className="wrap">
        <SectionHead coord={ORIGIN.coord} eyebrow={ORIGIN.eyebrow} title={ORIGIN.h2} />

        <Stagger className="origin" gap={STAGGER.siblings}>
          {ORIGIN.paragraphs.map((paragraph) => (
            <StaggerItem key={paragraph.slice(0, 32)}>
              <p>{paragraph}</p>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
