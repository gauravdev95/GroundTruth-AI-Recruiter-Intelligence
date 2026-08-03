import { ACCESS } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { MagneticButton } from "./MagneticButton";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";
import { Check, Dot } from "./StatusBadge";

/**
 * §07 — what we read, and what we don't keep.
 *
 * The most important trust section on the page, and the reason is a matter of
 * proportion rather than of tone: a visitor is being asked to hand over access
 * to their source code. A trust signal has to match the size of the risk it
 * answers, and no badge, seal or logo wall answers a request that large. Two
 * columns of specific, checkable commitments do.
 *
 * Both columns spend the semantic pair correctly. The left is what the product
 * does — read-only scope, derived metrics, revocation — and the right is what
 * it refuses. Each line is a statement about behaviour, so green and amber are
 * carrying meaning here rather than decorating a list.
 *
 * The CTA at the foot is deliberate. §07 has to be reachable within one scroll
 * of any CTA on the page, and the surest way to guarantee that is to put one
 * inside it: the reader who hesitated at a button two sections ago lands here,
 * gets the answer, and does not have to scroll back to act on it.
 */
export function Access() {
  return (
    <section className="sec" id="access">
      <div className="wrap">
        <SectionHead coord={ACCESS.coord} eyebrow={ACCESS.eyebrow} title={ACCESS.h2} lead={ACCESS.lead} />

        <Stagger className="two-col" gap={STAGGER.cards}>
          {ACCESS.ledger.map((column) => (
            <StaggerItem className="panel ledger-panel" key={column.key}>
              <h3 className={`ledger-title ${column.key === "do" ? "do" : "never"}`}>{column.title}</h3>

              <ul>
                {column.items.map((item) => (
                  <li className="ledger-item" key={item}>
                    {/*
                      The mark inherits its colour from the column heading, and
                      the two shapes differ — a check against an open ring — so
                      "we do" and "we never" are distinguishable without relying
                      on the reader separating green from amber.
                    */}
                    <span
                      className={`ledger-mark ${column.key === "do" ? "is-verified" : "is-flagged"}`}
                      aria-hidden="true"
                    >
                      {column.key === "do" ? <Check /> : <Dot />}
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </StaggerItem>
          ))}
        </Stagger>

        <div className="ledger-cta">
          <MagneticButton to={ACCESS.cta.href} arrow>
            {ACCESS.cta.label}
          </MagneticButton>
        </div>
      </div>
    </section>
  );
}
