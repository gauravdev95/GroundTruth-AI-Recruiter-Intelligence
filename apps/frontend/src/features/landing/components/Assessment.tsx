import { Fragment } from "react";

import { ASSESSMENT } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";

/**
 * The words given the heavier of the two neutral tones.
 *
 * This is the entire syntax highlighter, and that is the point. The panel uses
 * two neutral tones and a weight change — no green, no amber, no violet —
 * because a keyword painted in a status colour would quietly claim a meaning
 * the page has spent three sections defining. A reader who has learned that
 * green means "proven by an artefact" cannot then be shown a green `return`.
 */
const KEYWORDS =
  /\b(let|const|export|async|await|function|return|if|else|null|new|class|this|Promise|void)\b/g;

/**
 * Widened from the literal tuple `as const` produces. Without this, `.includes`
 * is typed against the three literal values it happens to contain and rejects
 * an arbitrary line number — the narrowing is right for the data and wrong for
 * the lookup.
 */
const HIGHLIGHTED: readonly number[] = ASSESSMENT.file.highlighted;

/**
 * §04 — the code-grounded interview.
 *
 * The second of three mechanism sections. Its argument is narrow and it makes
 * it in one screen: here is a file, here is the question the engine generated
 * from that file, here is exactly how the answer was scored. The question is
 * about a real concurrency subtlety in the code beside it — `??=` with a
 * `.finally()` reset — because a question a reader can see the difficulty of is
 * the only way to demonstrate that the questions are not generic.
 */
export function Assessment() {
  return (
    <section className="sec" id="assessment">
      <div className="wrap">
        <SectionHead
          coord={ASSESSMENT.coord}
          eyebrow={ASSESSMENT.eyebrow}
          title={ASSESSMENT.h2}
          lead={ASSESSMENT.lead}
        />

        <div className="asmt">
          <Reveal className="panel">
            <div className="code-head">
              <span className="mono">{ASSESSMENT.file.name}</span>
              <span className="mono">{ASSESSMENT.file.label}</span>
            </div>

            <div className="code-body">
              {ASSESSMENT.file.lines.map((line, index) => {
                const lineNumber = index + 1;
                const highlighted = HIGHLIGHTED.includes(lineNumber);

                return (
                  <div className={highlighted ? "code-line hl" : "code-line"} key={lineNumber}>
                    <span className="code-no num" aria-hidden="true">
                      {lineNumber}
                    </span>
                    <code>
                      <Highlighted line={line} />
                    </code>
                  </div>
                );
              })}
            </div>
          </Reveal>

          <Reveal className="panel q-panel" delay={80}>
            <div className="q-head">
              <span>{ASSESSMENT.question.label}</span>
              <span>{ASSESSMENT.question.source}</span>
            </div>

            <p className="q-body">{ASSESSMENT.question.body}</p>
            <p className="q-meta">{ASSESSMENT.question.meta}</p>

            <div className="q-state">
              <span>{ASSESSMENT.question.state}</span>
              <span>
                {ASSESSMENT.question.elapsedLabel} <span className="num">{ASSESSMENT.question.elapsed}</span>
              </span>
            </div>

            <div className="q-score">
              <span>{ASSESSMENT.question.scoreLabel}</span>
              {/*
                The bar is the score, drawn at its own value — the same rule the
                rubric bars below follow. --slate, not green: a score is a
                measurement, and the page's green means "proven by an artefact",
                which a number is not.
              */}
              <span className="rubric-track" style={{ flex: 1 }}>
                <span className="rubric-fill" style={{ ["--w" as string]: `${ASSESSMENT.question.scorePct}%` }} />
              </span>
              <span className="q-score-value num">{ASSESSMENT.question.score}</span>
            </div>
          </Reveal>
        </div>

        {/*
          The published rubric. `RUBRIC_WEIGHTS` in the backend is the source of
          these four numbers, and each bar is drawn at exactly its own weight —
          four equal bars under 40/25/20/15 would be a data-integrity bug on a
          page whose entire argument is that its numbers are real.
        */}
        <Reveal className="panel rubric">
          <h3 className="rubric-title">{ASSESSMENT.rubric.title}</h3>

          <Stagger gap={STAGGER.siblings}>
            {ASSESSMENT.rubric.rows.map((row) => (
              <StaggerItem className="rubric-row" key={row.criterion}>
                <span className="rubric-criterion">{row.criterion}</span>
                <span className="rubric-track">
                  <span className="rubric-fill" style={{ ["--w" as string]: `${row.weight}%` }} />
                </span>
                <span className="rubric-weight num">{row.weight}%</span>
              </StaggerItem>
            ))}
          </Stagger>
        </Reveal>
      </div>
    </section>
  );
}

interface HighlightedProps {
  line: string;
}

/** Splits a line into keyword and non-keyword runs. Two tones, nothing else. */
function Highlighted({ line }: HighlightedProps) {
  const parts = line.split(KEYWORDS);

  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={index}>
          {/*
            `String.split` with a capturing group interleaves the captures at
            odd indices, so the parity test is what identifies a keyword — no
            second pass over the string and no lookup table.
          */}
          <span className={index % 2 === 1 ? "tok-key" : "tok-dim"}>{part}</span>
        </Fragment>
      ))}
    </>
  );
}
