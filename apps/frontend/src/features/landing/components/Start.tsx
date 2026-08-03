import { START } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { MagneticButton } from "./MagneticButton";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";

/**
 * §12 — two sides, one record of truth.
 *
 * The closing CTA repeats §02's split rather than collapsing to one button, and
 * both panels are filled at equal weight. A two-sided page that spends twelve
 * sections insisting neither audience is secondary and then ends on a single
 * student CTA has told the recruiter what it actually thinks.
 *
 * The line beneath carries pricing. It is one sentence rather than a nav link
 * because there is no pricing page and inventing one would be the same class of
 * unverifiable claim the page spends its length arguing against — and it also
 * carries the last reassurance on the page, placed where the final hesitation
 * is, directly under the buttons.
 */
export function Start() {
  return (
    <section className="sec" id="start">
      <div className="wrap">
        <SectionHead coord={START.coord} eyebrow={START.eyebrow} title={START.h2} />

        <Stagger className="two-col" gap={STAGGER.cards}>
          {START.panels.map((panel) => (
            <StaggerItem className="panel start-panel" key={panel.key}>
              <p className="start-label">{panel.label}</p>
              <p className="start-body">{panel.body}</p>

              <div className="start-cta">
                <MagneticButton to={panel.cta.href} arrow>
                  {panel.cta.label}
                </MagneticButton>
              </div>
            </StaggerItem>
          ))}
        </Stagger>

        <Reveal>
          <p className="start-note">{START.note}</p>
        </Reveal>
      </div>
    </section>
  );
}
