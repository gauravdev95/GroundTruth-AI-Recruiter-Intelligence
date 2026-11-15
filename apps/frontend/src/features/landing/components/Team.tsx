import { TEAM } from "../content/landing";
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
      <div className="max-w-[680px]">
        <Reveal>
          <Overline tone="light">{TEAM.overline}</Overline>
        </Reveal>

        <Reveal delay={0.06}>
          <h2 className="mt-5 font-grotesk text-gt-h3 font-bold text-gt-void">{TEAM.headline}</h2>
        </Reveal>

        {/*
          One card, not a roster. There are no named team members to put in
          cards — this page carries no invented people — so the collective
          note is presented as the team's card: the brand mark, the note, the
          signature. A grid of faces here would have to be stock photos or
          fiction, and either would break the page's one rule.
        */}
        <Reveal delay={0.12}>
          <div className="mt-10 rounded-2xl border border-black/[0.08] bg-white p-8 shadow-[0_4px_24px_rgba(0,0,0,0.08)] md:p-10">
            <p className="flex items-center gap-2.5 font-grotesk text-lg font-bold tracking-tight text-gt-void">
              <span aria-hidden="true" className="h-2 w-2 rounded-full bg-gt-electric" />
              GroundTruth
            </p>

            {TEAM.note.map((paragraph) => (
              <p
                key={paragraph.slice(0, 24)}
                className="mt-5 font-sans text-gt-body-sm leading-[1.7] text-gt-slate"
              >
                {paragraph}
              </p>
            ))}

            <p className="mt-8 border-t border-black/[0.08] pt-6 font-sans text-gt-body-sm font-medium text-gt-void">
              {TEAM.signature}
            </p>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
