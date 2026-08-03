import { motion } from "framer-motion";

import { CONSOLE, HERO } from "../content/landing";
import { DURATION, EASE, STAGGER, useAfterIdle, useReducedMotionSafe, useSequence } from "../lib/motion";
import { Counter } from "./Counter";
import { Dot, NeutralBadge, StatusBadge } from "./StatusBadge";

/**
 * §00 — the verification console beside the headline.
 *
 * The headline states the argument; this performs it. A repository is scanned
 * in front of the reader: seven pipeline stages tick across the segment bar,
 * commits stream through the log, four self-declared skills are replaced by
 * the artefacts that prove them — and the one that cannot be proven stays on
 * the profile, flagged rather than quietly dropped.
 *
 * TWELVE BEATS, 0.16s APART
 *
 *   0      frame; four skills listed, all SELF-DECLARED in --flagged
 *   1–7    the seven stages tick; commit rows stream in
 *   8      skills resolve — three VERIFIED, one UNPROVEN
 *   9      score ring draws, 93 counts up, three pulse rings, radial wash
 *   10     metrics footer resolves
 *   11     the replay control fades in
 *
 * ~1.9s in total, which fits inside the ten-second budget a stranger gives the
 * page, and it starts only after `useAfterIdle(500)` — the sequence mounts and
 * unmounts a dozen layers in its first two seconds, and doing that at mount put
 * all of it inside the window that decides LCP and Total Blocking Time.
 *
 * TWO THINGS THAT MAKE IT SAFE TO PUT ABOVE THE FOLD
 *
 * **Nothing it does changes the layout.** Every container that will eventually
 * hold content reserves its height from the first frame — the ring is a fixed
 * 84px, the commit log has a `min-height`, the metrics row is always present
 * and only its values fade. So the twelve beats contribute exactly zero to CLS,
 * which is the whole reason a scene like this is usually forbidden in a hero.
 *
 * **Nothing it says is only said here.** A screen reader gets the finished
 * readout as one static summary, and the animated internals are `aria-hidden`.
 * The same facts are laid out again in §03 for anyone who never sees the
 * animation at all.
 *
 * React decides which layers exist; CSS decides how they move. That division is
 * what makes Replay work with no imperative reset: dropping the beat to zero
 * unmounts the layers, and remounting them restarts their CSS animations.
 */
export function HeroConsole() {
  const reduced = useReducedMotionSafe();
  const idle = useAfterIdle(500);

  const { step, replay } = useSequence({
    steps: 12,
    interval: STAGGER.consoleBeat,
    enabled: idle,
  });

  const stagesDone = Math.max(0, Math.min(CONSOLE.stages.length, step));
  const skillsResolved = step >= 8;
  const scored = step >= 9;
  const metricsIn = step >= 10;
  const replayIn = step >= 11;

  /* The stage currently being read, or the last one once the run has finished. */
  const currentStage = Math.min(CONSOLE.stages.length, Math.max(1, stagesDone));

  return (
    <div className="hc-scene">
      <div className="hc">
        <div className="hc-head">
          <span className="hc-dot" aria-hidden="true" />
          <span className="mono hc-repo">{CONSOLE.repo}</span>
          <span className="hc-state" aria-hidden="true">
            {scored ? <StatusBadge status={CONSOLE.verdict} /> : <NeutralBadge>Scanning</NeutralBadge>}
          </span>
        </div>

        <div className="hc-body" aria-hidden="true">
          {/* ---- score ---- */}
          <div className="hc-score">
            <div className="hc-ring">
              <svg viewBox="0 0 84 84" fill="none">
                <circle className="hc-ring-track" cx="42" cy="42" r="36" strokeWidth="3" />
                {scored && (
                  /*
                   * The ring is the one score on the page drawn in the verified
                   * green, and it earns it: by beat 9 every stage has returned
                   * an artefact, so the ring reports a proven result rather
                   * than decorating a number. `pathLength` is the page's single
                   * sanctioned exception to transform-and-opacity — Framer
                   * implements it as dash-offset, which repaints one stroke and
                   * touches neither layout nor the compositor tree.
                   */
                  <motion.circle
                    className="hc-ring-fill"
                    cx="42"
                    cy="42"
                    r="36"
                    strokeWidth="3"
                    strokeLinecap="round"
                    initial={{ pathLength: reduced ? CONSOLE.score / 100 : 0 }}
                    animate={{ pathLength: CONSOLE.score / 100 }}
                    transition={{ duration: reduced ? 0 : DURATION.cinematic, ease: EASE.entrance }}
                  />
                )}
              </svg>

              {scored && (
                <span className="hc-ring-value num">
                  <Counter to={CONSOLE.score} />
                </span>
              )}

              {scored && !reduced && (
                <>
                  <span className="hc-wash" />
                  <span className="hc-pulse" />
                  <span className="hc-pulse" />
                  <span className="hc-pulse" />
                </>
              )}
            </div>

            <div className="hc-score-meta">
              <p className="hc-score-label">{CONSOLE.scoreLabel}</p>

              {/*
                The container holds its 22px whether or not there are bars in
                it, so mounting them at beat 1 reserves the row from the first
                frame and still lets each bar play its grow-from-the-baseline
                animation — hiding pre-mounted bars with `opacity` would have
                run that animation invisibly at page load and popped them in.
              */}
              <div className="hc-spark">
                {step >= 1 &&
                  CONSOLE.spark.map((height, index) => (
                    <span
                      key={index}
                      className="hc-spark-bar"
                      style={{
                        height: `${Math.round(height * 100)}%`,
                        animationDelay: `${index * 0.04}s`,
                      }}
                    />
                  ))}
              </div>

              <p className="hc-spark-label">{CONSOLE.sparkLabel}</p>
            </div>
          </div>

          {/* ---- the seven stages ---- */}
          <div className="hc-stages">
            <div className="hc-segments">
              {/*
                The fill animation is triggered by the class arriving, not by a
                delay — each segment animates once, on the beat that completes
                its stage, and never replays. Which is also why Replay works:
                dropping to beat 0 removes `done` from all seven, and they
                re-run as the sequence catches up.
              */}
              {CONSOLE.stages.map((stage, index) => (
                <span key={stage} className={index < stagesDone ? "hc-seg done" : "hc-seg"} />
              ))}
            </div>

            <p className="hc-stage-name mono">
              <span className="hc-stage-n num">{String(currentStage).padStart(2, "0")}</span>
              {"  "}
              {CONSOLE.stages[currentStage - 1]}
            </p>
          </div>

          {/* ---- commit rows ---- */}
          <div className="hc-commits">
            {CONSOLE.commits.map((commit, index) => (
              <p
                key={commit}
                className="hc-commit"
                // Reserved from the first frame, revealed as the scan reads
                // each one — so the log grows without moving anything.
                style={{ visibility: step >= index * 2 + 2 ? "visible" : "hidden" }}
              >
                {commit}
              </p>
            ))}
          </div>

          <p className="hc-vector" style={{ opacity: step >= 7 ? 1 : 0 }}>
            {CONSOLE.vectorLine}
          </p>

          {/* ---- skills ---- */}
          <div className="hc-skills">
            {CONSOLE.skills.map((skill) => (
              <div className="hc-skill" key={skill.name}>
                <span className="hc-skill-name">{skill.name}</span>
                <span className="hc-skill-evidence">
                  {skillsResolved ? skill.evidence : skill.claim}
                </span>
                {skillsResolved ? (
                  <StatusBadge status={skill.status} />
                ) : (
                  <span className="badge badge-flagged">
                    <Dot />
                    Self-declared
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* ---- metrics footer ---- */}
          <div className="hc-metrics" style={{ opacity: metricsIn ? 1 : 0 }}>
            {CONSOLE.metrics.map((metric) => (
              <div key={metric.label}>
                <p className="hc-metric-value num">{metric.value}</p>
                <p className="hc-metric-label">{metric.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/*
          Under reduced motion the scene is already in its final state, so a
          control whose only job is to replay an animation has nothing to do —
          `replay()` is a no-op there by design. Rendering the button anyway
          would put a dead control in the keyboard path.
        */}
        {replayIn && !reduced && (
          <button type="button" className="hc-replay" onClick={replay}>
            <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
              <path
                d="M10 6a4 4 0 1 1-1.2-2.85"
                stroke="currentColor"
                strokeWidth="1.3"
                fill="none"
              />
              <path d="M10.6 1.4V4h-2.6" stroke="currentColor" strokeWidth="1.3" fill="none" />
            </svg>
            {CONSOLE.replayLabel}
          </button>
        )}

        {/*
          The finished readout, always in its final state and never animated.
          This is what a screen reader gets, and it is why every animated layer
          above is `aria-hidden` — a live region ticking through twelve beats
          would be unusable, and content that only exists mid-animation would be
          content gated behind motion.
        */}
        <p className="sr-only">
          Sample verification console for {CONSOLE.repo}. Evidence score {CONSOLE.score} out of 100,
          repository {CONSOLE.verdict.toLowerCase()}. {CONSOLE.vectorLine}.{" "}
          {CONSOLE.skills
            .map((skill) => `${skill.name}: ${skill.evidence}, ${skill.status.toLowerCase()}`)
            .join(". ")}
          . {CONSOLE.metrics.map((metric) => `${metric.label} ${metric.value}`).join(", ")}. This is
          sample data, not a real candidate.
        </p>
      </div>

      {/*
        The one sample-data disclosure on this surface, placed beside the CTAs
        where hesitation actually peaks. It is stated once here, once on the §03
        evidence panel, and once in the footer — three disclaimers read as
        defensive, one reads as confident.
      */}
      <p className="hc-sample">{HERO.sampleLabel}</p>
    </div>
  );
}

