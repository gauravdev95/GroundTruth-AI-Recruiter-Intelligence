import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { DURATION, EASE, STAGGER, TRAVEL, useReducedMotionSafe } from "@/design/motion";

import { AuthAurora } from "./AuthAurora";

interface AuthHeroProps {
  /** Overline above the headline. Uppercased and tracked by this component. */
  eyebrow: string;
  headline: ReactNode;
  /** The one-line promise under the headline. */
  lead: string;
  /** Three short proof lines beside the form on desktop. */
  points: readonly string[];
  /** Panel heading, above the form. */
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  /** Cross-link under the panel — "Already have an account?" and its inverse. */
  footer?: ReactNode;
}

function BrandMark() {
  return (
    <Link
      to="/"
      className="group inline-flex items-center gap-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric/60"
      aria-label="GroundTruth — home"
    >
      {/*
        The same mark `AuthLayout` draws, with the check re-coloured. The light
        layout uses `--verified` green on white; on this backdrop that green sits
        at about 2.4:1 and reads as a smudge. Electric is the page's own accent
        and is legible here — the mark's meaning is in its shape, not its hue.
      */}
      <svg width="24" height="24" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path d="M10 9 L4 16 L10 23" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="square" />
        <path d="M22 9 L28 16 L22 23" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="square" />
        <path
          d="M11.5 16.2 L15 19.6 L20.5 12"
          stroke="#2563EB"
          strokeWidth="2.4"
          strokeLinecap="square"
        />
      </svg>
      <span className="font-grotesk text-[15px] font-bold tracking-tight text-white">
        GroundTruth
      </span>
    </Link>
  );
}

/**
 * The sign-in / sign-up shell: a landing-hero surface with a form on it.
 *
 * WHY THIS EXISTS ALONGSIDE `AuthLayout` RATHER THAN REPLACING IT. Only the two
 * pages a logged-out visitor arrives at from marketing — `/login` and `/signup`
 * — are worth a full-height animated hero. `/forgot-password` and
 * `/reset-password` are recovery screens reached mid-task, and they keep the
 * quiet light card. `AuthLayout` is still the layout for those, unchanged.
 *
 * THE LEFT COLUMN IS NOT DECORATION. It carries the same three claims the
 * landing page makes, so a visitor who arrived on a deep link to `/signup`
 * without reading the marketing page still knows what they are signing up for
 * before they type an email address. It is `hidden` below `lg` — on a phone the
 * form is the entire job and copy above it just pushes the fields off-screen.
 *
 * MOTION. Entrances come from the shared tokens in `design/motion.ts`; nothing
 * here writes a literal duration or easing curve. Everything resolves to its
 * final state under `prefers-reduced-motion` — the copy and the form appear
 * settled, and `AuthAurora` paints a single frame and never subscribes to the
 * frame loop.
 */
export function AuthHero({
  eyebrow,
  headline,
  lead,
  points,
  title,
  subtitle,
  children,
  footer,
}: AuthHeroProps) {
  const reduced = useReducedMotionSafe();

  /** Entrance props for the nth element of the left-hand copy stack. */
  const entrance = (index: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: TRAVEL },
          animate: { opacity: 1, y: 0 },
          transition: {
            duration: DURATION.slow,
            ease: EASE.entrance,
            delay: index * STAGGER.siblings,
          },
        };

  return (
    <div className="relative isolate flex min-h-[100svh] flex-col overflow-hidden bg-[linear-gradient(180deg,#050510_0%,#0A1128_100%)]">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <AuthAurora />
      </div>

      {/*
        A hairline grid over the aurora, at very low contrast. Carried from the
        landing page's blueprint motif; it gives the blobs an edge to move
        against, without which large soft gradients read as a rendering
        artefact rather than as a scene.
      */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.18] [background-image:linear-gradient(rgba(255,255,255,0.5)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.5)_1px,transparent_1px)] [background-size:72px_72px] [mask-image:radial-gradient(75%_65%_at_50%_40%,#000_10%,transparent_75%)]"
      />

      <header className="relative z-10 flex items-center justify-between px-6 py-6 sm:px-10 sm:py-8">
        <BrandMark />
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-white/60 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric/60"
        >
          <ArrowLeft size={15} /> Back to home
        </Link>
      </header>

      <main className="relative z-10 flex flex-1 items-center px-6 pb-16 pt-4 sm:px-10 sm:pb-20">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-12 lg:grid-cols-[1fr_minmax(0,460px)] lg:gap-20">
          {/* ---- the pitch ------------------------------------------- */}
          <div className="hidden lg:block">
            <motion.p
              {...entrance(0)}
              className="font-sans text-gt-over-hero font-medium uppercase text-gt-electric"
            >
              {eyebrow}
            </motion.p>

            <motion.h1
              {...entrance(1)}
              className="mt-6 max-w-[13ch] font-grotesk text-gt-h2 font-bold uppercase text-white"
            >
              {headline}
            </motion.h1>

            <motion.p {...entrance(2)} className="mt-6 max-w-[46ch] font-sans text-gt-body text-gt-ash">
              {lead}
            </motion.p>

            <motion.ul {...entrance(3)} className="mt-10 flex flex-col gap-3.5">
              {points.map((point) => (
                <li key={point} className="flex items-start gap-3 font-sans text-gt-body-sm text-white/75">
                  {/* A rule, not a tick. A checkmark next to a marketing claim
                      on this product would read as "verified", which is a word
                      that means something specific here and is not earned by a
                      sentence on a sign-in page. */}
                  <span
                    aria-hidden="true"
                    className="mt-[0.7em] h-px w-5 shrink-0 bg-gt-electric"
                  />
                  {point}
                </li>
              ))}
            </motion.ul>
          </div>

          {/* ---- the form -------------------------------------------- */}
          <motion.div
            initial={reduced ? false : { opacity: 0, y: TRAVEL, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: DURATION.slow, ease: EASE.entrance }}
            className="mx-auto w-full max-w-[460px]"
          >
            <div className="rounded-2xl border border-white/12 bg-white/[0.055] p-6 shadow-[0_24px_70px_-24px_rgba(0,0,0,0.85)] backdrop-blur-xl sm:p-8">
              <div className="mb-6">
                <h2 className="font-grotesk text-2xl font-bold tracking-tight text-white">{title}</h2>
                {subtitle ? (
                  <p className="mt-2 text-sm leading-relaxed text-white/55">{subtitle}</p>
                ) : null}
              </div>
              {children}
            </div>

            {footer ? (
              <p className="mt-6 text-center text-sm text-white/55">{footer}</p>
            ) : null}
          </motion.div>
        </div>
      </main>
    </div>
  );
}

/**
 * The cross-link style used in both pages' footers and inline prose.
 *
 * Underline-on-rest rather than underline-on-hover: these sit on a busy
 * animated backdrop where a colour shift alone is not a reliable signal that
 * something is a link.
 */
export const heroLinkClass =
  "font-medium text-white underline decoration-white/30 underline-offset-4 transition hover:decoration-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric/60 rounded";
