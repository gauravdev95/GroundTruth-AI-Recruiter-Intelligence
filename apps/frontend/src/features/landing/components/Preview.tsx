import { BadgeCheck, Play } from "lucide-react";

import { ENGINEERS, PREVIEW, RECRUITERS } from "../content/landing";
import { stagger } from "../lib/reveal";
import { MockCard } from "./ui/MockCard";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";

/**
 * A still of the interview screen, standing in for the walkthrough.
 *
 * There is no recording yet. The brief asks for a play button over a
 * screenshot, and a play button that plays nothing is a broken control — worse
 * here than anywhere else on the page, because this section's claim is that you
 * can watch the product be honest.
 *
 * So the affordance is present and visibly inert: no hover state, no pointer
 * cursor, and a label saying what it is waiting for. Nothing is focusable, so a
 * keyboard user is never handed a control that does not work.
 */
function WalkthroughFrame() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/20 bg-[#0A0F1E] shadow-[0_4px_24px_rgba(0,0,0,0.08)]">
      {/* 16:9, held by aspect-ratio so the frame never reflows as it loads. */}
      <div className="aspect-video w-full p-6 sm:p-10">
        <div className="flex h-full flex-col justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-wider text-white/50 sm:text-[11px]">
              Adaptive interview · question 4 of 6
            </p>
            <p className="mt-4 max-w-[52ch] font-sans text-[13px] leading-relaxed text-white/90 sm:mt-5 sm:text-base">
              Your retry loop catches every error and backs off the same way. Which of those
              failures should not be retried, and what happens today when one of them is?
            </p>
          </div>

          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3 sm:p-4">
            <p className="font-mono text-[10px] text-white/45 sm:text-[11px]">
              payments-api · src/retry.rs:88
            </p>
            <p className="mt-2 truncate font-mono text-[11px] text-white/80 sm:text-[13px]">
              <span className="text-gt-electric">match</span> err {"{"} _ ={">"} backoff(attempt),
              {"}"}
            </p>
          </div>
        </div>
      </div>

      {/*
        The inert play affordance. `aria-hidden`, because the sentence beneath
        it already tells a screen-reader user that there is nothing to play.
      */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/45">
        <span
          aria-hidden="true"
          className="flex h-16 w-16 items-center justify-center rounded-full border border-white/25 bg-white/10 backdrop-blur-sm"
        >
          <Play size={22} className="ml-0.5 text-white/80" fill="currentColor" />
        </span>
        <p className="px-6 text-center font-mono text-[10px] uppercase tracking-wider text-white/70 sm:text-[11px]">
          {PREVIEW.unavailable}
        </p>
      </div>
    </div>
  );
}

/**
 * The two product screens the walkthrough frame stands between.
 *
 * Condensed versions of the mocks the audience sections already carry — the
 * engineer's evidence report and the recruiter's pipeline — so this section
 * shows the actual product surfaces rather than describing them. Same data,
 * same "Sample" caption rule: nothing here is a real candidate, and the
 * footer carries the same disclosure a fourth time.
 */
function ProductScreens() {
  const { report } = ENGINEERS;
  const { board } = RECRUITERS;

  return (
    <div className="mt-12 grid gap-8 lg:grid-cols-2">
      <MockCard
        tone="dark"
        tilt="left"
        caption={report.caption}
        title={
          <div>
            <p className="font-grotesk text-lg font-bold text-gt-chalk">{report.candidate}</p>
            <p className="mt-1 font-sans text-sm text-gt-ash">{report.subject}</p>
          </div>
        }
      >
        <dl className="mt-8 space-y-5">
          {report.skills.map((skill) => (
            <div key={skill.name}>
              <div className="flex items-baseline justify-between gap-4">
                <dt className="font-sans text-gt-body-sm font-medium text-gt-chalk">
                  {skill.name}
                </dt>
                <dd className="font-mono text-sm tabular-nums text-gt-electric">
                  {skill.confidence}%
                </dd>
              </div>
              <div role="presentation" className="mt-2 h-1 w-full rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gt-electric"
                  style={{ width: `${skill.confidence}%` }}
                />
              </div>
              <p className="mt-2 font-mono text-[11px] text-gt-dim">{skill.source}</p>
            </div>
          ))}
        </dl>
        <p className="mt-8 border-t border-white/10 pt-5 font-sans text-[13px] text-gt-ash">
          {report.footnote}
        </p>
      </MockCard>

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
        <div className="mt-8 space-y-6">
          {board.columns.map((column) => (
            <div key={column.name}>
              <p className="font-mono text-[11px] uppercase tracking-wider text-gt-dim">
                {column.name}
              </p>
              <div className="mt-3 space-y-3">
                {column.cards.map((card) => (
                  <div
                    key={card.initials}
                    className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-gt-void/60 px-4 py-3"
                  >
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-[13px] text-gt-chalk">{card.initials}</span>
                      {card.verified && (
                        <BadgeCheck
                          size={13}
                          aria-hidden="true"
                          className="shrink-0 text-gt-electric"
                        />
                      )}
                      <span className="font-mono text-[11px] text-gt-dim">{card.skills}</span>
                    </span>
                    <span className="font-mono text-[11px] tabular-nums text-gt-electric">
                      {card.match}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </MockCard>
    </div>
  );
}

export function Preview() {
  return (
    <Section id="preview" label="Product preview" tone="wash">
      <SectionHead
        overline={PREVIEW.overline}
        headline={PREVIEW.headline}
        lead={PREVIEW.lead}
        tone="wash"
      />

      <Reveal delay={0.1}>
        <div className="mt-12">
          <WalkthroughFrame />
        </div>
      </Reveal>

      <Reveal delay={0.15}>
        <ProductScreens />
      </Reveal>

      <ul className="mt-10 flex flex-wrap gap-x-10 gap-y-4">
        {PREVIEW.features.map((feature, index) => (
          <Reveal as="li" key={feature} delay={stagger(index, 0.06)}>
            <span className="flex items-center gap-2.5 font-sans text-sm text-white/80">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-white" />
              {feature}
            </span>
          </Reveal>
        ))}
      </ul>
    </Section>
  );
}
