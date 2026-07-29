import { CountUp } from "./CountUp";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function Problem() {
  return (
    <section className="sec" id="problem">
      <div className="wrap">
        <SectionHead
          eyebrow="The problem"
          title={
            <>
              Keyword matching was never <span className="serif">verification.</span>
            </>
          }
          lead="ATS pipelines score resume wording, not engineering ability — and AI-written resumes have made claims free to generate and expensive to check."
        />
        <div className="tiles">
          <Reveal delay={0}>
            <div className="glass tile">
              <span className="tile-tag">ATS REALITY</span>
              <span className="tile-num">0</span>
              <span className="tile-cap">
                lines of real code a keyword-matching ATS ever reads before ranking a candidate
              </span>
            </div>
          </Reveal>
          <Reveal delay={110}>
            <div className="glass tile">
              <span className="tile-tag">PER OPEN ROLE</span>
              <span className="tile-num">
                <CountUp to={100} suffix="s" />
              </span>
              <span className="tile-cap">
                of near-identical applications, all tuned to the same job-description keywords
              </span>
            </div>
          </Reveal>
          <Reveal delay={220}>
            <div className="glass tile">
              <span className="tile-tag">AI-WRITTEN RESUMES</span>
              <span className="tile-num">≠</span>
              <span className="tile-cap">
                a generated claim is not a demonstrated skill — the gap between the two keeps
                widening
              </span>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
