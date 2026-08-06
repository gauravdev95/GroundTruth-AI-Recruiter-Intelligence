import { ArrowRight } from "lucide-react";

import { STAGGER, useCountUp } from "@/design/motion";
import { Celebrate, ProgressRing, Reveal } from "@/design/primitives";
import { Surface } from "@/design/Surface";

import { AnalysisFeed } from "./AnalysisFeed";

/**
 * The moment onboarding ends and the analysis begins.
 *
 * WHY THE CELEBRATION AND THE WORK ARE ON THE SAME SCREEN
 *
 * The obvious design is a full-screen success moment, then a separate
 * loading page. Putting them together is better for one specific reason:
 * this is the only point in the product where the student has just finished
 * the effort and the platform is about to spend a minute proving it was
 * worth something. Splitting those apart wastes the handover — the student
 * celebrates, then lands on a spinner with no sense of connection between
 * what they did and what is now happening.
 *
 * Together, the screen reads as one sentence: you built this, and here is
 * the system going to work on it, line by line.
 *
 * THE NUMBER COUNTS UP, AND ONLY THE FIRST TIME
 *
 * `useCountUp` adopts its first observed value instantly and animates only
 * subsequent changes. A student returning to this screen sees 35 rendered
 * immediately rather than re-celebrating work they finished yesterday — the
 * animation marks a *change*, not a mount.
 *
 * THE RING IS VIOLET, NOT GREEN
 *
 * Profile strength measures what is FILLED, not what is verified — the
 * backend is explicit that those are different numbers
 * (`completeness.py`). A green ring here would claim verification the
 * student has not earned yet; the green arrives per-claim in the feed
 * below, as each check actually settles.
 */

interface ProfileCreatedStepProps {
  profileStrength: number;
  onGoToDashboard: () => void;
}

export function ProfileCreatedStep({
  profileStrength,
  onGoToDashboard,
}: ProfileCreatedStepProps) {
  const displayed = useCountUp(profileStrength);

  return (
    <div className="mx-auto max-w-[620px] px-6 py-14">
      <div className="text-center">
        <Celebrate active className="inline-block">
          <ProgressRing value={profileStrength} size={132} strokeWidth={9}>
            <span className="tabular font-[family-name:var(--disp)] text-3xl font-semibold text-[var(--ink)]">
              {Math.round(displayed)}
            </span>
            <span className="machine mt-0.5 text-[10px] uppercase tracking-wider text-[var(--muted)]">
              strength
            </span>
          </ProgressRing>
        </Celebrate>

        <Reveal trigger="mount" delay={STAGGER.siblings * 2}>
          <h1 className="mt-7 font-[family-name:var(--disp)] text-[28px] font-semibold leading-tight text-[var(--ink)]">
            Your profile is live.
          </h1>
          <p className="mx-auto mt-2.5 max-w-[44ch] text-sm leading-relaxed text-[var(--slate)]">
            We are checking every claim you made against its source right now. You do not need to
            wait here — we will email you the moment your interview is ready.
          </p>
        </Reveal>
      </div>

      <Reveal trigger="mount" delay={STAGGER.siblings * 3}>
        <Surface elevation="raised" className="mt-9 p-4">
          <AnalysisFeed />
        </Surface>
      </Reveal>

      <Reveal trigger="mount" delay={STAGGER.siblings * 4}>
        <button
          type="button"
          onClick={onGoToDashboard}
          className="group mt-7 flex w-full items-center justify-center gap-2 rounded-[var(--r-full)] px-6 py-3.5 text-sm font-semibold text-white"
          style={{ backgroundImage: "linear-gradient(100deg, var(--violet), var(--blue))" }}
        >
          Go to dashboard
          <ArrowRight
            size={15}
            aria-hidden="true"
            className="transition-transform group-hover:translate-x-0.5"
          />
        </button>

        {/*
          Named explicitly so the student knows what the next unlock is and
          what gates it. "Profile strength" is not the thing that makes them
          discoverable — a completed interview is — and leaving that implicit
          is what makes students think they are finished when they are not.
        */}
        <p className="mt-3 text-center text-[11px] leading-relaxed text-[var(--muted)]">
          Recruiters can find you once your evidence is checked and your interview is complete.
        </p>
      </Reveal>
    </div>
  );
}
