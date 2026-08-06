import { ENGINEERS } from "../content/landing";
import { Button } from "./ui/Button";
import { MockCard } from "./ui/MockCard";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { CheckList, SectionHead } from "./ui/SectionHead";

/**
 * The evidence report, as a candidate would see it.
 *
 * Every number in here is invented, and the card says so on its own face rather
 * than in a footnote somewhere below it. A skill name beside a confidence
 * percentage is read as a measurement — that is the entire point of the design
 * — so the disclosure has to travel with the image, including into a screenshot
 * of it.
 *
 * The bars are the page's one accent colour. Not green: green on this product
 * means "proven by an artefact", and spending it on an illustration would make
 * it worth less everywhere it is telling the truth.
 */
function EvidenceReport() {
  const { report } = ENGINEERS;

  return (
    <MockCard
      tone="light"
      tilt="left"
      caption={report.caption}
      title={
        <div>
          <p className="font-grotesk text-lg font-bold text-gt-void">{report.candidate}</p>
          <p className="mt-1 font-sans text-sm text-gt-slate">{report.subject}</p>
        </div>
      }
    >
      <dl className="mt-8 space-y-6">
        {report.skills.map((skill) => (
          <div key={skill.name}>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="font-sans text-gt-body-sm font-medium text-gt-void">{skill.name}</dt>
              <dd className="font-mono text-sm tabular-nums text-gt-electric">
                {skill.confidence}%
              </dd>
            </div>

            {/*
              `role="presentation"` on the track: the percentage is already in
              the `<dd>` above it, so the bar is a second rendering of a number
              the reader has been given, not a new fact.
            */}
            <div role="presentation" className="mt-2 h-1 w-full rounded-full bg-black/[0.07]">
              <div
                className="h-full rounded-full bg-gt-electric"
                style={{ width: `${skill.confidence}%` }}
              />
            </div>

            <p className="mt-2 font-mono text-[11px] text-gt-slate">{skill.source}</p>
          </div>
        ))}
      </dl>

      <p className="mt-8 border-t border-black/[0.08] pt-5 font-sans text-[13px] text-gt-slate">
        {report.footnote}
      </p>
    </MockCard>
  );
}

export function ForEngineers() {
  return (
    <Section id="engineers" label="For engineers" tone="paper">
      <div className="grid items-center gap-16 lg:grid-cols-2 lg:gap-20">
        <div>
          <SectionHead
            overline={ENGINEERS.overline}
            headline={ENGINEERS.headline}
            tone="light"
            accentOverline
          />

          <Reveal delay={0.12}>
            <p className="mt-6 max-w-[560px] font-sans text-gt-body text-gt-slate">
              {ENGINEERS.body}
            </p>
          </Reveal>

          <CheckList items={ENGINEERS.bullets} tone="light" />

          <Reveal delay={0.1}>
            <div className="mt-10">
              <Button href={ENGINEERS.cta.href}>{ENGINEERS.cta.label}</Button>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.08}>
          <EvidenceReport />
        </Reveal>
      </div>
    </Section>
  );
}
