import { Play } from "lucide-react";

import { PREVIEW } from "../content/landing";
import { stagger } from "../lib/reveal";
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
