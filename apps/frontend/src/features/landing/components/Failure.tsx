import { FAILURE } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";
import { StatusBadge } from "./StatusBadge";

/**
 * §01 — where hiring breaks.
 *
 * The top of this section has one structural job beyond its content: its
 * hairline and coordinate must break the fold. Research on the "illusion of
 * completeness" found that readers routinely fail to notice a page scrolls when
 * the first screen looks finished, and that horizontal rules in particular read
 * as endings. This page is built almost entirely from hairlines, so 40–80px of
 * §01 showing under the hero is the scroll cue — which is why the hero is
 * `88vh` and why there is no bouncing arrow anywhere.
 *
 * Two columns per row: the failure in the display face, the consequence in
 * sans. The typeface change is doing the work a "problem / impact" label
 * would otherwise have to do.
 */
export function Failure() {
  return (
    <section className="sec" id="failure">
      <div className="wrap">
        <SectionHead
          coord={FAILURE.coord}
          eyebrow={FAILURE.eyebrow}
          title={FAILURE.h2}
          lead={FAILURE.lead}
        />

        <Stagger className="fail-list" gap={STAGGER.siblings}>
          {FAILURE.links.map((link) => (
            <StaggerItem className="fail-row" key={link.failure}>
              <p className="fail-title">{link.failure}</p>
              <p className="fail-consequence">{link.consequence}</p>
            </StaggerItem>
          ))}
        </Stagger>

        {/*
          The conveyor: the five failures above, stated once as a picture.
          Two keyword-stuffed entries drift through the gate; the entry with a
          dense commit history and no keywords is the one it stops. Nothing here
          is a new claim — it is the same argument in a form a reader who
          skimmed the list will still take away.
        */}
        <Reveal className="panel conveyor">
          <div className="conveyor-head">
            <span>{FAILURE.conveyor.label}</span>
            <span aria-hidden="true">→</span>
          </div>

          <div className="conveyor-track">
            {FAILURE.conveyor.entries.map((entry) => (
              <div className={`conveyor-lane ${entry.kind}`} key={entry.text}>
                <span className="conveyor-rail" aria-hidden="true" />

                {/* Content-width, never a full-width box with four words in it. */}
                <span className="conveyor-chip">
                  {entry.kind === "evidence" && (
                    <span className="conveyor-spark" aria-hidden="true">
                      {[5, 9, 4, 11, 7, 12, 6].map((height, index) => (
                        <i key={index} style={{ height }} />
                      ))}
                    </span>
                  )}
                  {entry.text}
                </span>

                <span className="conveyor-verdict">
                  {/*
                    The keyword rows are amber — claimed, unchecked, and waved
                    through — and the evidence row is green because a commit
                    history is an artefact. The gate stopping the green row is
                    the point: the filter is rejecting the only proven entry.
                  */}
                  <StatusBadge status={entry.kind === "evidence" ? "VERIFIED" : entry.verdict} />
                </span>
              </div>
            ))}
          </div>

          <p className="conveyor-caption">{FAILURE.conveyor.caption}</p>
        </Reveal>
      </div>
    </section>
  );
}
