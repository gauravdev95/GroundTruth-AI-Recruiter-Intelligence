import { PROBLEM } from "../content/landing";
import { stagger } from "../lib/reveal";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";
import { Stat } from "./ui/Stat";

/** §03 — the case for the product, and the three figures behind it. */
export function Problem() {
  return (
    <Section id="problem" label="The hiring problem" tone="paper">
      <SectionHead
        overline={PROBLEM.overline}
        headline={PROBLEM.headline}
        lead={PROBLEM.lead}
        tone="light"
      />

      {/*
        `items-start` rather than a stretched grid: the three labels wrap to
        different line counts, and stretching would align their tops to a shared
        baseline that only exists because the longest one wrapped.
      */}
      <div className="mt-16 grid items-start gap-12 sm:grid-cols-2 lg:mt-20 lg:grid-cols-3 lg:gap-16">
        {PROBLEM.stats.map((stat, index) => (
          <Reveal key={stat.value} delay={stagger(index)}>
            <Stat {...stat} />
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
