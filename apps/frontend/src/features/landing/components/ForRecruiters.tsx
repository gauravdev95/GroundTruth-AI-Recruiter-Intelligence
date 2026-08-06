import { BadgeCheck } from "lucide-react";

import { RECRUITERS } from "../content/landing";
import { Button } from "./ui/Button";
import { MockCard } from "./ui/MockCard";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { CheckList, SectionHead } from "./ui/SectionHead";

/**
 * The recruiter pipeline, as a board of candidate cards.
 *
 * Same disclosure rule as the engineer report: the sample-data label is part of
 * the image. It matters more here, because these cards carry initials and match
 * percentages, and initials read as people.
 *
 * One card is deliberately unverified. A board where every candidate carries a
 * verification badge would show a product that has nothing to distinguish —
 * the badge only means something on a board where it can be absent.
 */
function PipelineBoard() {
  const { board } = RECRUITERS;

  return (
    <MockCard
      tone="dark"
      tilt="right"
      caption={board.caption}
      title={
        <div>
          <p className="font-grotesk text-lg font-bold text-gt-chalk">{board.role}</p>
          <p className="mt-1 font-sans text-sm text-gt-ash">Hiring pipeline</p>
        </div>
      }
    >
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {board.columns.map((column) => (
          <div key={column.name}>
            <p className="font-mono text-[11px] uppercase tracking-wider text-gt-dim">
              {column.name}
            </p>

            <div className="mt-3 space-y-3">
              {column.cards.map((card) => (
                <div
                  key={card.initials}
                  className="rounded-xl border border-white/10 bg-gt-void/60 p-3.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono text-[13px] text-gt-chalk">{card.initials}</span>
                      {card.verified && (
                        <BadgeCheck
                          size={13}
                          aria-hidden="true"
                          className="shrink-0 text-gt-electric"
                        />
                      )}
                    </span>
                    <span className="font-mono text-[11px] tabular-nums text-gt-electric">
                      {card.match}%
                    </span>
                  </div>
                  <p className="mt-2 font-mono text-[10px] text-gt-dim">{card.skills}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </MockCard>
  );
}

export function ForRecruiters() {
  return (
    <Section id="recruiters" label="For recruiters" tone="void">
      {/*
        Reversed against §05: the board sits left on desktop so the two audience
        sections do not read as the same layout twice. `order-*` rather than
        source order, because on mobile both sections must still lead with their
        headline — an image before its own heading gives a screen-reader user an
        unlabelled figure to walk past.
      */}
      <div className="grid items-center gap-16 lg:grid-cols-2 lg:gap-20">
        <div className="lg:order-2">
          <SectionHead
            overline={RECRUITERS.overline}
            headline={RECRUITERS.headline}
            tone="dark"
            accentOverline
          />

          <Reveal delay={0.12}>
            <p className="mt-6 max-w-[560px] font-sans text-gt-body text-gt-ash">
              {RECRUITERS.body}
            </p>
          </Reveal>

          <CheckList items={RECRUITERS.bullets} tone="dark" />

          <Reveal delay={0.1}>
            <div className="mt-10">
              <Button href={RECRUITERS.cta.href} tone="dark">
                {RECRUITERS.cta.label}
              </Button>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.08} className="lg:order-1">
          <PipelineBoard />
        </Reveal>
      </div>
    </Section>
  );
}
