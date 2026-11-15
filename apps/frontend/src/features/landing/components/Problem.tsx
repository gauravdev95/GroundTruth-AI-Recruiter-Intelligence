import { FileWarning, FolderGit2, ShieldAlert, Timer } from "lucide-react";

import type { ProblemIssue } from "../content/landing";
import { PROBLEM } from "../content/landing";
import { stagger } from "../lib/reveal";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";
import { Stat } from "./ui/Stat";

const ISSUE_ICONS: Record<ProblemIssue["icon"], typeof FileWarning> = {
  "file-warning": FileWarning,
  "folder-git": FolderGit2,
  "shield-alert": ShieldAlert,
  timer: Timer,
};

/** §03 — the case for the product, the four failure modes, and the three figures behind it. */
export function Problem() {
  return (
    <Section id="problem" label="The hiring problem" tone="paper">
      <SectionHead
        overline={PROBLEM.overline}
        headline={PROBLEM.headline}
        lead={PROBLEM.lead}
        tone="light"
      />

      {/*
        The four failure modes as cards, ahead of the statistics. Each line is
        a sentence from the lead above, split out — the cards name the problem
        and the figures below it measure it.
      */}
      <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:mt-20 lg:grid-cols-4">
        {PROBLEM.issues.map((issue, index) => {
          const Icon = ISSUE_ICONS[issue.icon];
          return (
            <Reveal key={issue.headline} delay={stagger(index, 0.06)}>
              <div className="h-full rounded-2xl border border-black/[0.08] bg-white p-6 shadow-[0_4px_24px_rgba(0,0,0,0.08)]">
                <Icon aria-hidden="true" size={24} strokeWidth={1.75} className="text-gt-electric" />
                <h3 className="mt-5 font-grotesk text-lg font-bold text-gt-void">
                  {issue.headline}
                </h3>
                <p className="mt-2 font-sans text-[15px] leading-relaxed text-gt-slate">
                  {issue.body}
                </p>
              </div>
            </Reveal>
          );
        })}
      </div>

      {/*
        `items-start` rather than a stretched grid: the three labels wrap to
        different line counts, and stretching would align their tops to a shared
        baseline that only exists because the longest one wrapped.
      */}
      <div className="mt-16 grid items-start gap-12 border-t border-black/[0.08] pt-16 sm:grid-cols-2 lg:mt-20 lg:grid-cols-3 lg:gap-16">
        {PROBLEM.stats.map((stat, index) => (
          <Reveal key={stat.value} delay={stagger(index)}>
            <Stat {...stat} />
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
