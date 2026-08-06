import { ArrowRight, Clock, ShieldCheck, Sparkles } from "lucide-react";

import { DURATION, EASE, STAGGER, useMagnetic, useReducedMotionSafe } from "@/design/motion";
import { Reveal, Stagger } from "@/design/primitives";
import { Surface } from "@/design/Surface";

/**
 * The welcome screen — the first thing a student sees after signing up.
 *
 * WHY A WELCOME SCREEN EXISTS AT ALL
 *
 * Dropping a new account straight into a profile builder is the single
 * biggest cause of abandonment in this flow: the student is looking at an
 * empty form with a 0% meter and no idea what any of it is for or how long it
 * will take. This screen costs one click and buys three things — what they
 * are building, roughly how long it takes, and why the effort is different
 * from filling in a job board profile.
 *
 * THE TIME ESTIMATE IS A PROMISE, SO IT IS DELIBERATELY CONSERVATIVE
 *
 * "5-7 minutes" is stated because an unbounded form is what makes people
 * leave. It is also load-bearing: if the flow actually takes twelve minutes,
 * this screen has lied at the moment it was asking for trust, and the whole
 * premise of the product is that it does not overstate things. The estimate
 * covers the GitHub connect, a resume upload, and a review pass — not the
 * background analysis, which is why the copy says the checking happens
 * afterwards rather than folding it into the number.
 */

const PROMISES = [
  {
    icon: ShieldCheck,
    title: "Every claim gets checked",
    body: "We verify your repositories, coding profiles and certificates against the source — so your profile carries proof, not adjectives.",
  },
  {
    icon: Sparkles,
    title: "You will not retype your resume",
    body: "Upload it once. We read it, show you what we found, and you correct anything we got wrong before it is saved.",
  },
  {
    icon: Clock,
    title: "Finish in more than one sitting",
    body: "Everything saves as you go. Close the tab at any point and pick up exactly where you left off.",
  },
];

export function WelcomeStep({ onBegin, firstName }: { onBegin: () => void; firstName?: string }) {
  const reduced = useReducedMotionSafe();
  const magneticRef = useMagnetic<HTMLButtonElement>(6);

  return (
    <div className="mx-auto flex max-w-[640px] flex-col items-center px-6 py-16 text-center">
      <Reveal trigger="mount">
        <p className="machine mb-4 text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">
          Step 1 of 5 · Getting started
        </p>
      </Reveal>

      <Reveal trigger="mount" delay={STAGGER.siblings}>
        <h1 className="font-[family-name:var(--disp)] text-[clamp(2rem,5vw,2.75rem)] font-semibold leading-[1.1] tracking-tight text-[var(--ink)]">
          {firstName ? `Welcome, ${firstName}.` : "Welcome to GroundTruth."}
          <br />
          {/*
            The one gradient fill on this screen, on exactly two words. The
            landing page holds the same rule — gradients are light, not
            surface, and spending one anywhere else dilutes it.
          */}
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage: "linear-gradient(100deg, var(--violet), var(--blue))",
            }}
          >
            Let's build proof.
          </span>
        </h1>
      </Reveal>

      <Reveal trigger="mount" delay={STAGGER.siblings * 2}>
        <p className="mt-5 max-w-[46ch] text-[15px] leading-relaxed text-[var(--slate)]">
          You are about to build a profile where every skill links back to the artefact that
          proves it. Recruiters see the evidence, not just the claim.
        </p>
      </Reveal>

      <Stagger className="mt-10 w-full space-y-3" interval={STAGGER.cards}>
        {PROMISES.map(({ icon: Icon, title, body }) => (
          <Stagger.Item key={title}>
            <Surface className="flex items-start gap-4 p-4 text-left">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-[var(--r-sm)] bg-[var(--violet)]/12">
                <Icon size={15} className="text-[var(--violet)]" aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-medium text-[var(--ink)]">{title}</p>
                <p className="mt-1 text-[13px] leading-relaxed text-[var(--slate)]">{body}</p>
              </div>
            </Surface>
          </Stagger.Item>
        ))}
      </Stagger>

      <Reveal trigger="mount" delay={STAGGER.cards * 3 + 0.1}>
        <div className="mt-10 flex flex-col items-center gap-3">
          <button
            ref={magneticRef}
            type="button"
            onClick={onBegin}
            className="group inline-flex items-center gap-2 rounded-[var(--r-full)] px-7 py-3.5 text-sm font-semibold text-white shadow-[0_8px_32px_-8px_rgb(var(--glow-a)/0.6)]"
            style={{
              backgroundImage: "linear-gradient(100deg, var(--violet), var(--blue))",
            }}
          >
            Let's begin
            <ArrowRight
              size={15}
              aria-hidden="true"
              className={reduced ? "" : "transition-transform group-hover:translate-x-0.5"}
              style={
                reduced
                  ? undefined
                  : {
                      transitionDuration: `${DURATION.fast}s`,
                      transitionTimingFunction: `cubic-bezier(${EASE.standard.join(",")})`,
                    }
              }
            />
          </button>

          <p className="machine text-[11px] text-[var(--muted)]">
            About 5–7 minutes · saves as you go
          </p>
        </div>
      </Reveal>
    </div>
  );
}
