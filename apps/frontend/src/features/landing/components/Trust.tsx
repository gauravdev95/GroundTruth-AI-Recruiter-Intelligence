import { Scale, Shield, UserCheck } from "lucide-react";

import type { Pillar } from "../content/landing";
import { TRUST } from "../content/landing";
import { stagger } from "../lib/reveal";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";

const ICONS: Record<Pillar["icon"], typeof Shield> = {
  shield: Shield,
  "user-check": UserCheck,
  scale: Scale,
};

/** §09 — the three commitments, each with an outline icon. */
export function Trust() {
  return (
    <Section id="trust" label="Trust and compliance" tone="paper">
      <SectionHead overline={TRUST.overline} headline={TRUST.headline} tone="light" size="h3" />

      <div className="mt-16 grid gap-12 md:grid-cols-3 lg:mt-20">
        {TRUST.pillars.map((pillar, index) => {
          const Icon = ICONS[pillar.icon];
          return (
            <Reveal key={pillar.headline} delay={stagger(index)}>
              {/* The icon restates the heading beside it, so it is hidden from
                  assistive technology rather than given a duplicate label. */}
              <Icon aria-hidden="true" size={32} strokeWidth={1.5} className="text-gt-electric" />
              <h3 className="mt-6 font-grotesk text-xl font-bold text-gt-void">
                {pillar.headline}
              </h3>
              <p className="mt-3 font-sans text-[15px] leading-relaxed text-gt-slate">
                {pillar.body}
              </p>
            </Reveal>
          );
        })}
      </div>
    </Section>
  );
}
