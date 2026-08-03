import { SOURCES } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";
import { Dot } from "./StatusBadge";

/**
 * §08 — where the evidence comes from.
 *
 * Platform categories, never brand logos. Two reasons, and both matter: this
 * page has no permission to display anyone else's mark, and a row of borrowed
 * logos is the standard way a pre-launch product implies partnerships it does
 * not have. "Competitive programming — via platform APIs" is both accurate and
 * more informative than two logos a reader has to interpret.
 *
 * Each row states what is read and what that proves, in adjacent columns. The
 * middle column is mono because it lists what a machine ingests; the right is
 * sans because the inference is ours.
 *
 * The amber line at the foot is the section's real argument. A verification
 * product that silently drops what it cannot check is indistinguishable from
 * one that never checked — keeping the unverifiable entry visible and flagged
 * is what makes the verified ones mean anything.
 */
export function Sources() {
  return (
    <section className="sec" id="sources">
      <div className="wrap">
        <SectionHead
          coord={SOURCES.coord}
          eyebrow={SOURCES.eyebrow}
          title={SOURCES.h2}
          lead={SOURCES.lead}
        />

        <div className="src">
          {/*
            Not `aria-hidden`. It is hidden below 900px by the stylesheet, but
            these three labels are the only thing telling a reader that the
            middle column is input and the right column is inference — hiding
            them from assistive technology as well would leave three
            undifferentiated strings per row.
          */}
          <div className="src-head">
            <span>Source</span>
            <span>What is read</span>
            <span>What it proves</span>
          </div>

          <Stagger gap={STAGGER.siblings}>
            {SOURCES.rows.map((row) => (
              <StaggerItem className="src-row" key={row.source}>
                <span className="src-name">{row.source}</span>
                <span className="src-reads">{row.reads}</span>
                <span className="src-proves">{row.proves}</span>
              </StaggerItem>
            ))}
          </Stagger>
        </div>

        <Reveal className="src-flag">
          <span className="badge badge-flagged">
            <Dot />
            {SOURCES.flaggedChip}
          </span>
          {SOURCES.flagged}
        </Reveal>
      </div>
    </section>
  );
}
