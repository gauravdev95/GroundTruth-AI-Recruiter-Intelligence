import { FINAL_CTA } from "../content/landing";
import { Button } from "./ui/Button";
import { Overline } from "./ui/Overline";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";

/** §12 — the last ask. Centred, and the only centred section on the page. */
export function FinalCta() {
  return (
    <Section id="start" label="Get started" tone="void" padding="tall">
      <div className="mx-auto max-w-[900px] text-center">
        <Reveal>
          <Overline tone="accent">{FINAL_CTA.overline}</Overline>
        </Reveal>

        <Reveal delay={0.06}>
          <h2 className="mt-6 font-grotesk text-gt-mega font-bold text-gt-chalk">
            {FINAL_CTA.headline}
          </h2>
        </Reveal>

        <Reveal delay={0.12}>
          <p className="mx-auto mt-6 max-w-[560px] font-sans text-gt-lead text-gt-ash">
            {FINAL_CTA.lead}
          </p>
        </Reveal>

        <Reveal delay={0.18}>
          <div className="mt-12">
            <Button href={FINAL_CTA.primary.href} size="lg" tone="dark">
              {FINAL_CTA.primary.label}
            </Button>
          </div>
        </Reveal>

        <Reveal delay={0.24}>
          <p className="mt-6">
            <a
              href={FINAL_CTA.secondary.href}
              className="group rounded-sm font-sans text-sm text-gt-ash transition-colors duration-200 hover:text-gt-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-void"
            >
              {FINAL_CTA.secondary.label}{" "}
              <span
                aria-hidden="true"
                className="inline-block transition-transform duration-200 group-hover:translate-x-0.5"
              >
                →
              </span>
            </a>
          </p>
        </Reveal>
      </div>
    </Section>
  );
}
