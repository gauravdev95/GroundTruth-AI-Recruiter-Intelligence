import {
  HOW_IT_WORKS,
  STEP_ONE_SNIPPET,
  STEP_THREE_MATCH,
  STEP_TWO_QUESTION,
} from "../content/landing";
import { stagger } from "../lib/reveal";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";

/**
 * The three step visuals.
 *
 * Each is built from type and hairlines — no illustration, no icon set, no
 * imagery. They are deliberately small and quiet: the section's argument is
 * carried by the copy, and a visual here that competed with it would be
 * decoration on a page whose subject is the difference between evidence and
 * decoration.
 *
 * Monochrome throughout except the single accent, per the brief.
 */

const PANEL = "rounded-xl border border-white/10 bg-white/[0.03] p-5";

/** 01 — a fragment of the candidate's own code. */
function CodeCard() {
  return (
    <div className={PANEL} aria-hidden="true">
      <p className="font-mono text-[13px] leading-relaxed">
        {STEP_ONE_SNIPPET.map((token, index) => (
          <span
            key={index}
            className={
              token.tone === "keyword"
                ? "text-gt-electric"
                : token.tone === "name"
                  ? "text-gt-chalk"
                  : "text-gt-ash"
            }
          >
            {token.text}
          </span>
        ))}
      </p>
      <p className="mt-4 font-mono text-[11px] uppercase tracking-wider text-gt-dim">
        payments-api · src/settle.rs
      </p>
    </div>
  );
}

/** 02 — the interviewer's question about that same fragment. */
function QuestionBubble() {
  return (
    <div className={PANEL} aria-hidden="true">
      <p className="font-mono text-[11px] uppercase tracking-wider text-gt-electric">Interviewer</p>
      <p className="mt-3 font-sans text-[13px] leading-relaxed text-gt-chalk">
        <span className="font-mono text-gt-ash">settle_batch</span>
        {STEP_TWO_QUESTION.slice("settle_batch".length)}
      </p>
    </div>
  );
}

/** 03 — a candidate and a role, and the strength of the link between them. */
function MatchPair() {
  return (
    <div className="flex items-center gap-3" aria-hidden="true">
      <div className="flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-5">
        <p className="font-sans text-[13px] font-medium text-gt-chalk">Verified engineer</p>
        <p className="mt-1 font-mono text-[11px] text-gt-dim">Rust · Postgres</p>
      </div>

      <div className="flex shrink-0 flex-col items-center gap-1.5">
        <span aria-hidden="true" className="block h-px w-10 bg-gt-electric" />
        <span className="whitespace-nowrap font-mono text-[10px] text-gt-electric">
          {STEP_THREE_MATCH}
        </span>
      </div>

      <div className="flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-5">
        <p className="font-sans text-[13px] font-medium text-gt-chalk">Open role</p>
        <p className="mt-1 font-mono text-[11px] text-gt-dim">Backend · Series A</p>
      </div>
    </div>
  );
}

const VISUALS = [CodeCard, QuestionBubble, MatchPair];

export function HowItWorks() {
  return (
    <Section id="how-it-works" label="How GroundTruth works" tone="void">
      <SectionHead
        overline={HOW_IT_WORKS.overline}
        headline={HOW_IT_WORKS.headline}
        lead={HOW_IT_WORKS.lead}
        tone="dark"
      />

      {/*
        A real ordered list. These are three numbered steps in sequence, and
        the numerals are content rather than ornament — a screen reader that
        announces "list, 3 items" is telling the reader the same thing the 01/
        02/03 tells a sighted one.
      */}
      <ol className="mt-16 grid gap-12 md:grid-cols-3 lg:mt-20">
        {HOW_IT_WORKS.steps.map((step, index) => {
          const Visual = VISUALS[index];
          return (
            <Reveal as="li" key={step.index} delay={stagger(index)}>
              <p className="font-mono text-sm text-gt-electric">{step.index}</p>
              <h3 className="mt-4 font-grotesk text-gt-h4 font-bold text-gt-chalk">
                {step.headline}
              </h3>
              <p className="mt-3 font-sans text-gt-body-sm text-gt-ash">{step.body}</p>
              <div className="mt-8">
                <Visual />
              </div>
            </Reveal>
          );
        })}
      </ol>
    </Section>
  );
}
