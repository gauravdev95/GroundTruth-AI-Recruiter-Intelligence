import { AUDIENCE } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { MagneticButton } from "./MagneticButton";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";

/**
 * §02 — which side of the table are you on?
 *
 * This section is placed here on purpose, and the position is the decision.
 * Most two-sided pages route at the bottom, after the mechanism, which means
 * half the readers spend the whole page reading about someone else's problem.
 * Routing immediately after the failure and before any mechanism means every
 * section that follows is read by someone who has already been told which half
 * of it is theirs.
 *
 * Both panels are identical in size, treatment and button variant, and neither
 * is marked primary. The language is parallel line for line — "get judged on
 * what you built" against "shortlist against proof" — because a page that
 * visually picks a side has answered its own question for the reader.
 *
 * The reassurance line sits directly above each CTA rather than in a trust band
 * further down. Hesitation peaks at the button, not between sections.
 */
export function Audience() {
  return (
    <section className="sec" id="audience">
      <div className="wrap">
        <SectionHead
          coord={AUDIENCE.coord}
          eyebrow={AUDIENCE.eyebrow}
          title={AUDIENCE.h2}
          lead={AUDIENCE.lead}
        />

        <Stagger className="two-col" gap={STAGGER.cards}>
          {AUDIENCE.panels.map((panel) => (
            <StaggerItem className="panel aud-panel" key={panel.key}>
              <p className="aud-label">{panel.label}</p>

              <div className="aud-points">
                {panel.points.map((point) => (
                  <p className="aud-point" key={point}>
                    {point}
                  </p>
                ))}
              </div>

              <p className="aud-reassure">{panel.reassurance}</p>

              <div className="aud-cta">
                <MagneticButton to={panel.cta.href} arrow>
                  {panel.cta.label}
                </MagneticButton>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
