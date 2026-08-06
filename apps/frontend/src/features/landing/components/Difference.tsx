import { Check } from "lucide-react";

import { DIFFERENCE } from "../content/landing";
import { stagger } from "../lib/reveal";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";

/**
 * §07 — the comparison.
 *
 * NOT a `<table>`, though it looks like one. A table's value to a screen-reader
 * user is that every cell can be traced back to a column and row header; here
 * there are no row headers, so each cell would be announced with only "Traditional
 * platforms" or "GroundTruth" in front of it — which is precisely what the
 * visible label already says. It is a list of five paired statements, and it is
 * marked up as one.
 *
 * The mobile layout is the same list with the column name printed above each
 * half, rather than a table squeezed to one column. Restacking a real table is
 * what breaks the header association that made it a table in the first place.
 */
export function Difference() {
  return (
    <Section id="difference" label="Why GroundTruth" tone="paper">
      <SectionHead
        overline={DIFFERENCE.overline}
        headline={DIFFERENCE.headline}
        lead={DIFFERENCE.lead}
        tone="light"
      />

      <div className="mt-16 lg:mt-20">
        {/*
          The GroundTruth column is tinted and rules itself off with a left
          border, top to bottom.

          The point is that the comparison should resolve before it is read.
          Two columns of identical grey text make the reader parse ten
          statements to work out which side the page is arguing for; a tinted
          channel with an accent edge says which column is the answer at a
          glance, and the text then confirms it rather than carrying it alone.

          The tint is `gt-electric` at 4% — enough to separate from white,
          nowhere near enough to compete with the checkmarks inside it.
        */}
        <div className="hidden border-b border-black/10 lg:grid lg:grid-cols-2 lg:gap-0">
          <p className="pb-5 pr-12 font-sans text-gt-body-sm text-gt-slate">
            {DIFFERENCE.columns.before}
          </p>
          <p className="border-l-2 border-gt-electric bg-gt-electric/[0.04] pb-5 pl-6 pt-0 font-sans text-gt-body-sm font-bold text-gt-void">
            {DIFFERENCE.columns.after}
          </p>
        </div>

        <ul>
          {DIFFERENCE.rows.map(([before, after], index) => (
            <Reveal
              as="li"
              key={before}
              delay={stagger(index, 0.06)}
              className="grid gap-4 border-b border-black/10 py-8 lg:grid-cols-2 lg:gap-0 lg:py-0"
            >
              <div className="lg:py-10 lg:pr-12">
                <p className="font-mono text-[10px] uppercase tracking-wider text-gt-dim lg:hidden">
                  {DIFFERENCE.columns.before}
                </p>
                <p className="mt-1.5 font-sans text-gt-body-sm text-gt-slate lg:mt-0">{before}</p>
              </div>

              <div className="border-gt-electric bg-gt-electric/[0.04] lg:border-l-2 lg:py-10 lg:pl-6">
                <p className="font-mono text-[10px] uppercase tracking-wider text-gt-dim lg:hidden">
                  {DIFFERENCE.columns.after}
                </p>
                <p className="mt-1.5 flex items-start gap-2.5 font-sans text-gt-body-sm font-medium text-gt-void lg:mt-0">
                  <Check
                    aria-hidden="true"
                    size={18}
                    strokeWidth={2.5}
                    className="mt-0.5 shrink-0 text-gt-electric"
                  />
                  {after}
                </p>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    </Section>
  );
}
