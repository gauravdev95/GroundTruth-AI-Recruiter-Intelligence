import { Check } from "lucide-react";

import { PRICING } from "../content/landing";
import { Button } from "./ui/Button";
import { stagger } from "../lib/reveal";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";

/** §10 — early access. Two cards, neither of them charging anything today. */
export function Pricing() {
  return (
    <Section id="pricing" label="Early access and pricing" tone="void">
      <SectionHead
        overline={PRICING.overline}
        headline={PRICING.headline}
        lead={PRICING.lead}
        tone="dark"
        accentOverline
      />

      {/*
        `items-stretch` so both cards run to the same depth regardless of which
        has more features. The recruiter card has five and the engineer card
        four; ragged card bottoms in a two-card price comparison read as one
        plan being unfinished.
      */}
      <div className="mt-16 grid items-stretch gap-8 md:grid-cols-2 lg:mt-20">
        {PRICING.plans.map((plan, index) => (
          <Reveal key={plan.name} delay={stagger(index)} className="h-full">
            <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/5 p-8 md:p-10">
              <h3 className="font-sans text-gt-body-sm font-medium text-gt-ash">{plan.name}</h3>

              <p className="mt-6 font-grotesk text-gt-stat font-bold text-gt-chalk">{plan.price}</p>
              <p className="mt-3 font-sans text-gt-body-sm text-gt-ash">{plan.note}</p>

              <ul className="mt-8 flex-1 space-y-4">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check
                      aria-hidden="true"
                      size={18}
                      strokeWidth={2.5}
                      className="mt-0.5 shrink-0 text-gt-electric"
                    />
                    <span className="font-sans text-gt-body-sm text-gt-chalk">{feature}</span>
                  </li>
                ))}
              </ul>

              {/*
                Exactly one filled button per section, per the brief. The
                engineer plan takes it because it is the one that costs nothing
                and needs no conversation; the recruiter card asks for a demo,
                which is a heavier commitment and reads honestly as the quieter
                of the two.
              */}
              <div className="mt-10">
                <Button
                  href={plan.cta.href}
                  variant={plan.emphasis ? "primary" : "secondary"}
                  tone="dark"
                  block
                >
                  {plan.cta.label}
                </Button>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
