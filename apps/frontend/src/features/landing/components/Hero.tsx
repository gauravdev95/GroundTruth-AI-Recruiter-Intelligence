import { motion } from "framer-motion";
import { BadgeCheck, BrainCircuit, GitBranch, ShieldCheck } from "lucide-react";
import { useCallback, useState } from "react";
import type { ReactNode } from "react";

import { DURATION, EASE, TRAVEL, useReducedMotionSafe } from "@/design/motion";
import { cn } from "@/lib/utils";

import { HERO, HERO_CARDS } from "../content/landing";
import { ConstellationStill } from "./ConstellationStill";
import { SkillConstellation } from "./SkillConstellation";
import { Button } from "./ui/Button";
import { Container } from "./ui/Container";

/**
 * Whether the hero's copy was already on screen before React rendered.
 *
 * `index.html` ships the hero as static markup so the headline — the page's
 * LCP element — paints with the stylesheet instead of waiting for the bundle.
 * That creates a conflict with the brief's staggered entrance animation:
 * React mounting an animated headline over text the reader is already looking
 * at would fade it out and back in, which is worse than no animation at all.
 *
 * Resolved by asking, at module load, whether the static hero is in the
 * document. It is on a cold visit, so the copy renders settled and nothing
 * replays. It is not on a client-side navigation back to `/`, because React
 * owns the DOM by then — and there the entrance plays as specified. Evaluated
 * at module scope deliberately: this module is imported before `createRoot`
 * renders, which is the only moment the answer is still true.
 */
const PAINTED_BEFORE_REACT =
  typeof document !== "undefined" && document.querySelector("[data-static-hero]") !== null;

/** The brief's load stagger: overline, then headline, support, lead and CTAs behind it. */
const ENTRANCE_STEP = 0.1;

/**
 * One floating evidence card.
 *
 * The float is a slow vertical drift on a 6s loop — the only continuously
 * moving element on the page besides the constellation itself, and it is
 * gated on `reduced` like everything else: under `prefers-reduced-motion`
 * the cards render settled. `aria-hidden`: every card restates copy the page
 * already makes in text, and the "Sample" chip is a visual disclosure for a
 * sighted reader, not content a screen reader needs announced twice.
 */
function FloatCard({
  delay,
  reduced,
  className,
  children,
}: {
  delay: number;
  reduced: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <motion.div
      initial={false}
      animate={reduced ? { y: 0 } : { y: [0, -8, 0] }}
      transition={
        reduced ? { duration: 0 } : { duration: 6, repeat: Infinity, ease: "easeInOut", delay }
      }
      className={cn(
        "rounded-2xl border border-white/12 bg-white/[0.06] p-4 shadow-[0_18px_50px_-20px_rgba(0,0,0,0.8)] backdrop-blur-xl",
        className,
      )}
    >
      {children}
    </motion.div>
  );
}

function SampleChip({ label }: { label: string }) {
  return (
    <span className="shrink-0 rounded-md border border-white/15 bg-white/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-white/50">
      {label}
    </span>
  );
}

/**
 * The verification visuals beside the copy: a repository check, an AI
 * interview indicator, and a verified skill.
 *
 * Desktop only (`lg` up). On a phone the copy is the entire job and three
 * cards above it would push both CTAs below the fold — on the one device
 * where that matters most. The numbers are the page's existing sample data
 * (see `HERO_CARDS`), never a live claim.
 */
function HeroVisual({ reduced }: { reduced: boolean }) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute right-8 top-1/2 z-10 hidden w-[300px] -translate-y-1/2 flex-col gap-4 lg:flex xl:right-16 xl:w-[320px]"
    >
      <FloatCard delay={0} reduced={reduced}>
        <div className="flex items-start justify-between gap-3">
          <span className="flex items-center gap-2 text-sm font-medium text-white">
            <GitBranch size={16} className="text-gt-electric" />
            {HERO_CARDS.repo.repo}
          </span>
          <SampleChip label={HERO_CARDS.repo.caption} />
        </div>
        <p className="mt-3 flex items-center gap-2 text-[13px] text-white/75">
          <BadgeCheck size={15} className="shrink-0 text-gt-electric" />
          {HERO_CARDS.repo.status}
        </p>
        <p className="mt-1.5 font-mono text-[11px] text-white/45">{HERO_CARDS.repo.detail}</p>
      </FloatCard>

      <FloatCard delay={1.2} reduced={reduced} className="ml-8">
        <div className="flex items-start justify-between gap-3">
          <span className="flex items-center gap-2 text-sm font-medium text-white">
            <BrainCircuit size={16} className="text-gt-electric" />
            {HERO_CARDS.interview.label}
          </span>
          <SampleChip label={HERO_CARDS.interview.caption} />
        </div>
        <p className="mt-3 flex items-center gap-2 text-[13px] text-white/75">
          {/* The pulse is the "AI is working" indicator. `motion-safe` so a
              reader who asked for no motion gets a steady dot instead. */}
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gt-electric opacity-60 motion-reduce:animate-none" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-gt-electric" />
          </span>
          {HERO_CARDS.interview.detail}
        </p>
      </FloatCard>

      <FloatCard delay={2.4} reduced={reduced} className="ml-4">
        <div className="flex items-start justify-between gap-3">
          <span className="flex items-center gap-2 text-sm font-medium text-white">
            <ShieldCheck size={16} className="text-gt-electric" />
            {HERO_CARDS.skill.skill}
          </span>
          <SampleChip label={HERO_CARDS.skill.caption} />
        </div>
        <p className="mt-3 text-[13px] text-white/75">Verified skill</p>
        <p className="mt-1.5 font-mono text-[11px] text-white/45">{HERO_CARDS.skill.detail}</p>
      </FloatCard>
    </div>
  );
}

export function Hero() {
  const reduced = useReducedMotionSafe();
  const [scenePainted, setScenePainted] = useState(false);

  const onFirstFrame = useCallback(() => setScenePainted(true), []);

  /** Entrance props for the nth element of the copy stack. */
  const entrance = (index: number) => {
    if (reduced || PAINTED_BEFORE_REACT) return {};
    return {
      initial: { opacity: 0, y: TRAVEL },
      animate: { opacity: 1, y: 0 },
      transition: {
        duration: DURATION.slow,
        ease: EASE.standard,
        delay: index * ENTRANCE_STEP,
      },
    };
  };

  return (
    <header
      id="top"
      /*
       * `100svh` rather than `100vh`: on mobile Safari and Chrome, `vh` is the
       * viewport with the browser chrome retracted, so a `100vh` hero is taller
       * than the screen on arrival and the CTAs sit below the fold — on the one
       * device where that matters most.
       */
      className="relative isolate flex h-[100svh] min-h-[720px] flex-col justify-end overflow-hidden bg-[linear-gradient(180deg,#050510_0%,#0A1128_100%)]"
    >
      {/*
        Two layers, cross-faded — unless the reader asked for no motion, in
        which case the still is the scene. The canvas used to run
        unconditionally here, overriding `prefers-reduced-motion` for a
        continuously running background; a decorative layer is not worth
        overriding an accessibility signal the visitor set on purpose. The
        still is the same geometry, so nothing about the composition changes.
      */}
      {reduced ? (
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <ConstellationStill />
        </div>
      ) : (
        <>
          <div
            aria-hidden="true"
            className={cn(
              "pointer-events-none absolute inset-0 transition-opacity duration-700 ease-out",
              scenePainted ? "opacity-0" : "opacity-100",
            )}
          >
            <ConstellationStill />
          </div>

          <div
            className={cn(
              "pointer-events-none absolute inset-0 transition-opacity duration-700 ease-out",
              scenePainted ? "opacity-100" : "opacity-0",
            )}
          >
            <SkillConstellation onFirstFrame={onFirstFrame} />
          </div>
        </>
      )}

      <HeroVisual reduced={reduced} />

      {/*
        The copy sits on the page's own grid rather than the brief's fixed 80px
        inset. On a 1600px screen those are 160px apart, and the fixed version
        would put the hero's left edge somewhere no other section's left edge
        ever lands — which is the alignment the whole page is built on.
      */}
      <Container className="relative z-10 pb-24 pt-28 md:pb-[100px]">
        <div className="max-w-[560px]">
          <motion.p
            {...entrance(0)}
            className="font-sans text-gt-over-hero font-medium uppercase text-gt-ember"
          >
            {HERO.overline}
          </motion.p>

          {/*
            One `<h1>`, the brief's headline verbatim. The wordmark lockup the
            hero used to carry is gone — the nav brands every scroll position
            already, and a second giant "GroundTruth" above the headline was
            pushing the actual claim halfway down the viewport.
          */}
          <motion.h1
            {...entrance(1)}
            className="mt-8 max-w-[16ch] font-grotesk text-gt-h2 font-bold text-white"
          >
            {HERO.headline}
          </motion.h1>

          <motion.p
            {...entrance(2)}
            className="mt-6 max-w-[520px] font-sans text-gt-lead font-medium text-white"
          >
            {HERO.support}
          </motion.p>

          <motion.p
            {...entrance(3)}
            className="mt-4 max-w-[480px] font-sans text-gt-body-sm text-gt-ash"
          >
            {HERO.lead}
          </motion.p>

          <motion.div {...entrance(4)} className="mt-10 flex flex-wrap gap-4">
            <Button href={HERO.primary.href} size="lg" tone="dark" ring="ember">
              {HERO.primary.label}
            </Button>
            <Button
              href={HERO.secondary.href}
              variant="secondary"
              size="lg"
              tone="dark"
              ring="ember"
            >
              {HERO.secondary.label}
              <span
                aria-hidden="true"
                className="transition-transform duration-200 group-hover:translate-x-0.5"
              >
                →
              </span>
            </Button>
          </motion.div>
        </div>
      </Container>
    </header>
  );
}
