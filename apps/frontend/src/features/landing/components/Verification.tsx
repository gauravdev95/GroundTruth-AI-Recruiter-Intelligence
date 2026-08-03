import { useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { VERIFICATION } from "../content/landing";
import { DURATION, EASE, STAGGER, useReducedMotionSafe } from "../lib/motion";
import { DrawPath } from "./DrawPath";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";
import { NeutralBadge, StatusBadge } from "./StatusBadge";

const SKILLS = VERIFICATION.detected.skills;

/**
 * §03 — the seven stages, and the record they produce.
 *
 * The first of exactly three "how it works" sections. The cap is real: a page
 * fails not from too few sections but from several doing the same job, and five
 * consecutive mechanism blocks read as one long section the reader abandons in
 * the middle. §03 explains the pipeline, §04 explains the interview, §05
 * explains the matching, and nothing else on the page explains a mechanism.
 *
 * Two halves. The stage list is the process; the split panel beneath it is the
 * artefact that process produces — which is the more persuasive of the two,
 * because it is the thing a recruiter would actually read.
 *
 * ONE ANIMATION EXCEPTION, DECLARED
 *
 * The stage bodies animate `height`, which is the page's second and last
 * departure from transform-and-opacity (the first is SVG `pathLength`). It is
 * not an oversight: a disclosure's entire job is to reflow the content beneath
 * it, and no transform can move a sibling. The alternatives were an instant
 * jump, or `scaleY`, which stretches the text it is revealing. The cost is
 * bounded — one element, on click, while nothing else on the page is moving.
 */
export function Verification() {
  return (
    <section className="sec" id="verification">
      <div className="wrap">
        <SectionHead
          coord={VERIFICATION.coord}
          eyebrow={VERIFICATION.eyebrow}
          title={VERIFICATION.h2}
          lead={VERIFICATION.lead}
          note={VERIFICATION.note}
        />

        <Stagger className="stage-list" gap={STAGGER.siblings}>
          {VERIFICATION.stages.map((stage, index) => (
            <StaggerItem className="stage" key={stage.n}>
              <Stage stage={stage} defaultOpen={index === 0} />
            </StaggerItem>
          ))}
        </Stagger>

        <div className="artefact">
          <Reveal className="panel">
            <h3 className="panel-title">{VERIFICATION.profile.title}</h3>

            {VERIFICATION.profile.sections.map((section) => (
              <div className="prof-row" key={section.name}>
                <div className="prof-row-top">
                  <span className="prof-name">{section.name}</span>
                  {/*
                    Neutral, not green. MANDATORY describes a requirement, not a
                    verification outcome — painting it in the verified colour
                    would make green mean two different things and quietly
                    devalue every real badge on the page.
                  */}
                  <NeutralBadge>{section.status}</NeutralBadge>
                </div>
                <p className="prof-body">{section.body}</p>
              </div>
            ))}

            <p className="prof-foot">{VERIFICATION.profile.footnote}</p>
          </Reveal>

          <Reveal className="panel" delay={80}>
            <EvidencePanel />
          </Reveal>
        </div>
      </div>
    </section>
  );
}

interface StageProps {
  stage: (typeof VERIFICATION.stages)[number];
  defaultOpen: boolean;
}

/**
 * One stage of the pipeline.
 *
 * The check draws itself rather than appearing, which is the difference between
 * "this stage passed" as a label and as an event. It is green because a
 * completed stage is exactly what the verified colour is reserved for: a claim
 * that has been closed out by an artefact.
 *
 * The artefact line is mono and the description is sans, and that split is the
 * page's semantic type rule in miniature — `412 commits attributed · 74% of
 * changed lines` is something a machine extracted, "commit history isolates
 * what this person wrote" is something a human wrote.
 */
function Stage({ stage, defaultOpen }: StageProps) {
  const reduced = useReducedMotionSafe();
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = `stage-${stage.n}`;

  return (
    <>
      <button
        type="button"
        className="stage-btn"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="stage-n num">{stage.n}</span>

        <svg className="stage-check" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <DrawPath d="M3 9.4 L7 13.4 L15 4.6" strokeWidth={2} />
        </svg>

        <span className="stage-title">{stage.title}</span>
        <span className="stage-artefact mono">{stage.artefact}</span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={bodyId}
            className="stage-body"
            initial={reduced ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduced ? { height: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : DURATION.base, ease: EASE.entrance }}
          >
            <p className="stage-body-in">{stage.body}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/**
 * The evidence panel: chips wired to the artefacts behind them.
 *
 * This is the product's central claim made operable rather than described. A
 * page can assert "every skill links back to the artefact that proves it"; a
 * reader who clicks Kubernetes and gets "no repository evidence" has checked it.
 *
 * Implemented as a real tablist. Arrow keys move between chips with a roving
 * tabindex, so the whole panel costs one Tab stop rather than six, and `Home`
 * and `End` jump to the ends — which is what a keyboard user expects from a
 * horizontal group and does not get from six independent buttons.
 */
function EvidencePanel() {
  const [selected, setSelected] = useState(0);
  const chipRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const move = (next: number) => {
    const index = (next + SKILLS.length) % SKILLS.length;
    setSelected(index);
    chipRefs.current[index]?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        move(selected + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        move(selected - 1);
        break;
      case "Home":
        event.preventDefault();
        move(0);
        break;
      case "End":
        event.preventDefault();
        move(SKILLS.length - 1);
        break;
      default:
        break;
    }
  };

  const skill = SKILLS[selected];

  return (
    <>
      <h3 className="panel-title">{VERIFICATION.detected.title}</h3>

      {/*
        `onKeyDown` sits on the container rather than on each chip: arrow keys
        move focus between siblings, so the handler needs to know the group, and
        six identical handlers would each have to be told about the other five.
      */}
      <div className="ev-chips" role="tablist" aria-label="Detected skills" onKeyDown={onKeyDown}>
        {SKILLS.map((entry, index) => (
          <button
            key={entry.name}
            type="button"
            role="tab"
            id={`ev-chip-${index}`}
            aria-selected={index === selected}
            aria-controls="ev-panel"
            tabIndex={index === selected ? 0 : -1}
            ref={(node) => {
              chipRefs.current[index] = node;
            }}
            className="ev-chip"
            onClick={() => setSelected(index)}
          >
            {/*
              A filled dot for verified, an open ring for unproven — a shape
              difference, so the two states are distinguishable without colour.
              The chip's own text label lives in the panel below it.
            */}
            <span
              className={entry.status === "VERIFIED" ? "ev-dot verified" : "ev-dot unproven"}
              aria-hidden="true"
            />
            {entry.name}
          </button>
        ))}
      </div>

      <div className="ev-panel" role="tabpanel" id="ev-panel" aria-labelledby={`ev-chip-${selected}`}>
        <div className="ev-repo">
          <span>{skill.repo}</span>
          <StatusBadge status={skill.status} />
        </div>

        <p className="ev-summary">{skill.summary}</p>

        {(skill.files.length > 0 || skill.commits.length > 0) && (
          <div className="ev-lines">
            {[...skill.files, ...skill.commits].map((line) => (
              <p className="ev-line" key={line}>
                {line}
              </p>
            ))}
          </div>
        )}

        {/*
          The second of the page's three sample-data disclosures, and the reason
          it belongs here specifically: this panel is the most convincing thing
          on the page, so it is the one most worth being honest about.
        */}
        <p className="ev-hint">
          {VERIFICATION.detected.hint} Sample profile — no real candidate is shown.
        </p>
      </div>
    </>
  );
}
