import { motion } from "framer-motion";
import { useCallback, useState } from "react";

import { DURATION, EASE, TRAVEL, useReducedMotionSafe } from "@/design/motion";
import { cn } from "@/lib/utils";

import { HERO } from "../content/landing";
import { ConstellationStill } from "./ConstellationStill";
import { SkillConstellation } from "./SkillConstellation";
import { Button } from "./ui/Button";
import { Container } from "./ui/Container";

/**
 * Whether the hero's copy was already on screen before React rendered.
 *
 * `index.html` ships the hero as static markup so the wordmark — the page's LCP
 * element — paints with the stylesheet instead of waiting for the bundle. That
 * creates a conflict with the brief's staggered entrance animation: React
 * mounting an animated headline over text the reader is already looking at
 * would fade it out and back in, which is worse than no animation at all.
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

/** The brief's load stagger: wordmark, then headline, lead and CTAs behind it. */
const ENTRANCE_STEP = 0.1;

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
        Two layers, cross-faded.

        The still is a placeholder for the single frame between mount and the
        canvas's first paint — nothing more. It used to be a real fallback,
        shown on narrow viewports and after an idle delay, and those two gates
        are why the animated scene was never appearing: any one of them failing
        left the hero showing a frozen drawing with fully-painted arcs and no
        rotation. The canvas now mounts unconditionally and starts drawing in
        its mount effect, so the still is visible for well under a frame.

        REDUCED MOTION IS DELIBERATELY OVERRIDDEN HERE. `prefers-reduced-motion`
        still governs every other animation on this page — the copy entrance,
        the scroll reveals, the FAQ disclosure — but not this scene, because a
        continuously running background was asked for explicitly. That is a real
        trade against an accessibility signal the visitor set on purpose, and it
        is confined to one decorative `aria-hidden` layer. To honour the setting
        again, gate the canvas on `!reduced` and render `ConstellationStill`
        instead; both components already take the same geometry.
      */}
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
            One `<h1>`, two lines. The line break is structural, not a wrap:
            the brief stacks the wordmark, and letting it wrap naturally would
            break somewhere else at every width. `<br>` inside the heading keeps
            it a single accessible name — "GroundTruth" — rather than two.
          */}
          <motion.h1
            {...entrance(1)}
            className="mt-8 font-grotesk text-gt-wordmark font-bold uppercase text-white"
          >
            {HERO.wordmark[0]}
            <br />
            {HERO.wordmark[1]}
          </motion.h1>

          {/*
            Two beats, one block. The category statement carries the weight and
            the proof claim sits under it at the same size but lower contrast,
            so the eye takes the first line before the second — which is the
            order a visitor who has never heard of this product needs them in.
          */}
          <motion.p
            {...entrance(2)}
            className="mt-10 max-w-[520px] font-sans text-gt-lead font-medium text-white"
          >
            {HERO.headline}
            <span className="mt-2 block font-normal text-white/60">{HERO.support}</span>
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
