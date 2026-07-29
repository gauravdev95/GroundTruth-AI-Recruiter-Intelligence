import { PIPELINE_STEPS } from "../data/pipelineSteps";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function Pipeline() {
  return (
    <section
      className="sec"
      id="how"
      style={{ background: "var(--ink-2)", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}
    >
      <div className="wrap">
        <SectionHead
          eyebrow="How it works — candidate pipeline"
          title={
            <>
              From first commit to <span className="serif">proven profile.</span>
            </>
          }
          lead="Eight connected steps turn a GitHub account into a traceable record of real engineering work."
        />
        <div className="pipe">
          <svg className="pipe-svg" viewBox="0 0 1000 420" preserveAspectRatio="none" aria-hidden="true">
            <path
              d="M 60 105 H 940 C 975 105, 975 315, 940 315 H 60"
              fill="none"
              stroke="url(#pipeg)"
              strokeWidth="1.5"
              strokeDasharray="6 7"
              opacity="0.5"
            />
            <defs>
              <linearGradient id="pipeg" x1="0" y1="0" x2="1000" y2="420" gradientUnits="userSpaceOnUse">
                <stop stopColor="#4F46E5" />
                <stop offset="1" stopColor="#7C3AED" />
              </linearGradient>
            </defs>
          </svg>
          <div className="pipe-grid">
            {PIPELINE_STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 90}>
                <div className={`glass node ${i === 7 ? "node-final" : ""}`}>
                  <div className="node-top">
                    <span className="node-n">{s.n}</span>
                    <s.I size={19} className="node-ic" />
                  </div>
                  <h3>{s.t}</h3>
                  <p>{s.d}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
