import { DIFFERENCE } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";

/**
 * §06 — the same candidate, seen two ways.
 *
 * A comparison section, and the first one on the page that explains no
 * mechanism at all: after three mechanism sections the reader needs the payoff
 * stated plainly, not a fourth diagram.
 *
 * Deliberately not a feature-comparison table. There are no green ticks and no
 * red crosses — those would break the page's colour rule outright, and they are
 * also the single most recognisable visual tell of a template landing page. The
 * comparison is carried by one tonal step: the left column is `--slate`, the
 * right is `--ink`. That reads as "faded" against "present", which is exactly
 * the claim, and it cannot be mistaken for a status.
 */
export function Difference() {
  return (
    <section className="sec" id="difference">
      <div className="wrap">
        <SectionHead
          coord={DIFFERENCE.coord}
          eyebrow={DIFFERENCE.eyebrow}
          title={DIFFERENCE.h2}
          lead={DIFFERENCE.lead}
        />

        <div className="diff">
          <div className="diff-head">
            <span />
            <span>{DIFFERENCE.columns.left}</span>
            <span>{DIFFERENCE.columns.right}</span>
          </div>

          <Stagger gap={STAGGER.siblings}>
            {DIFFERENCE.rows.map((row) => (
              <StaggerItem className="diff-row" key={row.dimension}>
                <span className="diff-dimension">{row.dimension}</span>
                {/*
                  The column header is `display: none` below 900px, and the only
                  thing separating the two cells visually is the tonal step from
                  --slate to --ink — which a screen reader cannot hear and a
                  phone user cannot see a header for. These two labels carry the
                  distinction at every width and in every modality.
                */}
                <span className="diff-before">
                  <span className="sr-only">{DIFFERENCE.columns.left}: </span>
                  {row.before}
                </span>
                <span className="diff-after">
                  <span className="sr-only">{DIFFERENCE.columns.right}: </span>
                  {row.after}
                </span>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </div>
    </section>
  );
}
