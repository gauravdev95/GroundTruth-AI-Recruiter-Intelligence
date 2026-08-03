import { MATCHING } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";

/**
 * §05 — one computation, both directions.
 *
 * The last of the three mechanism sections, and the one that has to land the
 * page's structural claim rather than a feature: the similarity that ranks
 * candidates for a recruiter is the same similarity that ranks jobs for a
 * student. Nothing else on the page proves that a two-sided marketplace is one
 * system rather than two products sharing a login.
 *
 * Which is why both outputs are shown side by side. Showing only the recruiter's
 * list would quietly undo §02 for half the readers — and the symmetry is not a
 * layout preference here, it is the argument.
 *
 * Every score is `--ink`. A cosine similarity is a measurement, not a
 * verification result, and the page's green is reserved for things an artefact
 * has closed out.
 */
export function Matching() {
  return (
    <section className="sec" id="matching">
      <div className="wrap">
        <SectionHead
          coord={MATCHING.coord}
          eyebrow={MATCHING.eyebrow}
          title={MATCHING.h2}
          lead={MATCHING.lead}
        />

        {/*
          The connector is drawn at rest, not only while something is animating.
          A line that exists only during a reveal is a line most readers never
          see, and this one is carrying the claim that the two panels meet in a
          single computation.
        */}
        <Reveal className="converge">
          <span className="converge-connector" aria-hidden="true" />

          <div className="panel converge-panel">
            <p className="converge-title">{MATCHING.convergence.left.title}</p>
            {MATCHING.convergence.left.rows.map((row) => (
              <p className="converge-row mono" key={row}>
                {row}
              </p>
            ))}
          </div>

          <div className="converge-mid">
            <span className="converge-value num">{MATCHING.convergence.centre.value}</span>
            <span className="converge-label">{MATCHING.convergence.centre.label}</span>
          </div>

          <div className="panel converge-panel">
            <p className="converge-title">{MATCHING.convergence.right.title}</p>
            {MATCHING.convergence.right.rows.map((row) => (
              <p className="converge-row mono" key={row}>
                {row}
              </p>
            ))}
          </div>
        </Reveal>

        <Stagger className="outputs" gap={STAGGER.cards}>
          {MATCHING.outputs.map((output) => (
            <StaggerItem className="panel" key={output.title}>
              <p className="output-title">{output.title}</p>
              {output.rows.map((row) => (
                <div className="output-row" key={row.id}>
                  <span className="output-id">{row.id}</span>
                  <span className="output-score num">{row.score}</span>
                </div>
              ))}
            </StaggerItem>
          ))}
        </Stagger>

        {/* The chain, with neutral arrows — an arrow is a direction, and green
            would make it a claim about something having been proven. */}
        <Stagger className="chain" gap={STAGGER.siblings}>
          {MATCHING.chain.steps.map((step) => (
            <StaggerItem className="panel chain-step" key={step.step}>
              <p className="chain-name">{step.step}</p>
              <p className="chain-detail">{step.detail}</p>
            </StaggerItem>
          ))}
        </Stagger>

        <div className="pipeline">
          <Reveal>
            <p className="pipeline-title">{MATCHING.pipeline.title}</p>
          </Reveal>

          {/*
            Five states, and a card in every one. An empty Kanban column does not
            read as an empty stage — it reads as a page that failed to load,
            which on a page arguing for reliability is the most expensive
            possible impression.
          */}
          <Stagger className="pipeline-cols" gap={STAGGER.siblings}>
            {MATCHING.pipeline.columns.map((column) => (
              <StaggerItem className="pipeline-col" key={column.state}>
                <p className="pipeline-state">{column.state}</p>
                <div className="panel pipeline-card">
                  <div className="pipeline-card-top">
                    <span>{column.card.id}</span>
                    <span className="num">{column.card.score}</span>
                  </div>
                  <p className="pipeline-card-meta">
                    {column.card.authored}
                    <br />
                    {column.card.interview}
                  </p>
                </div>
              </StaggerItem>
            ))}
          </Stagger>

          <Reveal>
            <p className="pipeline-caption">{MATCHING.pipeline.caption}</p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
