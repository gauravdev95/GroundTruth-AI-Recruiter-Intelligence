import { TEAM } from "../content/landing";
import { stagger } from "../lib/reveal";
import { Overline } from "./ui/Overline";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";

/**
 * The human note, immediately before the last ask.
 *
 * Placed here on purpose: the reader has just been through pricing and the FAQ
 * and is about to be asked to sign up, which is the moment "who is behind this"
 * is actually being wondered. Any earlier and it interrupts the argument; below
 * the final CTA it would sit between the ask and the footer, where nobody
 * reads.
 *
 * Text only — no portrait, no named byline. It is not a testimonial and must
 * never become one: this page carries no quotes and no invented people, and the
 * collective signature is what keeps that true. See the note on `TEAM`.
 *
 * Narrow measure and no second column. The whole point is that this reads as
 * someone talking rather than as another marketing panel, and a 60-character
 * line does more for that than any amount of layout.
 */
export function Team() {
  return (
    <Section id="team" label="Who built this" tone="paper" className="border-t border-black/10">
      <div className="max-w-[640px]">
        <Reveal>
          <Overline tone="light">{TEAM.overline}</Overline>
        </Reveal>

        <Reveal delay={0.06}>
          <h2 className="mt-5 font-grotesk text-gt-h3 font-bold text-gt-void">{TEAM.headline}</h2>
        </Reveal>

        {TEAM.note.map((paragraph, index) => (
          <Reveal key={paragraph.slice(0, 24)} delay={0.12 + stagger(index, 0.05)}>
            <p className="mt-5 font-sans text-gt-body-sm leading-[1.7] text-gt-slate">
              {paragraph}
            </p>
          </Reveal>
        ))}

        <Reveal delay={0.3}>
          <p className="mt-8 font-sans text-gt-body-sm font-medium text-gt-void">
            {TEAM.signature}
          </p>
        </Reveal>
      </div>
    </Section>
  );
}
