import { Check, ShieldCheck } from "lucide-react";

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
 * The five step visuals.
 *
 * Each is built from type and hairlines — no illustration, no icon set, no
 * imagery. They are deliberately small and quiet: the section's argument is
 * carried by the copy, and a visual here that competed with it would be
 * decoration on a page whose subject is the difference between evidence and
 * decoration.
 *
 * Monochrome throughout except the single accent, per the brief. The ticks
 * here are UI chrome on a diagram, not verification claims about a person —
 * the same narrow reading that lets the audience sections use checkmark
 * bullets — so they stay electric, never green.
 */

const PANEL = "rounded-xl border border-white/10 bg-white/[0.03] p-5";

/** 01 — the profile, assembled from what the candidate connects. */
function ProfileCard() {
  const rows = ["GitHub connected", "Projects linked", "Skills extracted"];
  return (
    <div className={PANEL} aria-hidden="true">
      <p className="font-sans text-[13px] font-medium text-gt-chalk">Your profile</p>
      <ul className="mt-3 space-y-2.5">
        {rows.map((row) => (
          <li key={row} className="flex items-center gap-2 font-sans text-[13px] text-gt-ash">
            <Check size={14} strokeWidth={2.5} className="shrink-0 text-gt-electric" />
            {row}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 02 — a fragment of the candidate's own code. */
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

/** 03 — each skill, tied to the evidence behind it. No percentages here: the
 *  evidence report is where a confidence figure belongs, with its label. */
function VerifyCard() {
  const rows = [
    { skill: "Rust", source: "payments-api · commits" },
    { skill: "PostgreSQL", source: "payments-api · schema" },
    { skill: "React", source: "dashboard-ui · commits" },
  ];
  return (
    <div className={PANEL} aria-hidden="true">
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.skill}>
            <p className="flex items-center gap-2 font-sans text-[13px] font-medium text-gt-chalk">
              <ShieldCheck size={14} className="shrink-0 text-gt-electric" />
              {row.skill}
            </p>
            <p className="ml-6 mt-0.5 font-mono text-[11px] text-gt-dim">{row.source}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 04 — the interviewer's question about that same fragment. */
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

/**
 * 05 — a candidate and a role, and the strength of the link between them.
 * Stacked rather than side by side: five columns are too narrow for the
 * horizontal pair, and the vertical connector reads the same way.
 */
function MatchPair() {
  return (
    <div className="flex flex-col items-stretch gap-2" aria-hidden="true">
      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-4">
        <p className="font-sans text-[13px] font-medium text-gt-chalk">Verified engineer</p>
        <p className="mt-1 font-mono text-[11px] text-gt-dim">Rust · Postgres</p>
      </div>

      <div className="flex flex-col items-center gap-1">
        <span aria-hidden="true" className="block h-4 w-px bg-gt-electric" />
        <span className="whitespace-nowrap font-mono text-[10px] text-gt-electric">
          {STEP_THREE_MATCH}
        </span>
        <span aria-hidden="true" className="block h-4 w-px bg-gt-electric" />
      </div>

      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-4">
        <p className="font-sans text-[13px] font-medium text-gt-chalk">Open role</p>
        <p className="mt-1 font-mono text-[11px] text-gt-dim">Backend · Series A</p>
      </div>
    </div>
  );
}

const VISUALS = [ProfileCard, CodeCard, VerifyCard, QuestionBubble, MatchPair];

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
        A real ordered list. These are five numbered steps in sequence, and
        the numerals are content rather than ornament — a screen reader that
        announces "list, 5 items" is telling the reader the same thing the 01/
        02/03/04/05 tells a sighted one.
      */}
      <ol className="mt-16 grid gap-10 sm:grid-cols-2 lg:mt-20 lg:grid-cols-5 lg:gap-6">
        {HOW_IT_WORKS.steps.map((step, index) => {
          const Visual = VISUALS[index];
          return (
            <Reveal as="li" key={step.index} delay={stagger(index, 0.06)}>
              <p className="font-mono text-sm text-gt-electric">{step.index}</p>
              <h3 className="mt-4 font-grotesk text-xl font-bold text-gt-chalk">
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
