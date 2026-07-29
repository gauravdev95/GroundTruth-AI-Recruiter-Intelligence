import { ArrowRight } from "lucide-react";

import { Reveal } from "./Reveal";

export function FinalCTA() {
  return (
    <section className="final" style={{ borderTop: "1px solid var(--line)" }}>
      <div className="final-bg" />
      <div className="wrap" style={{ position: "relative" }}>
        <Reveal>
          <div className="eyebrow" style={{ justifyContent: "center" }}>
            GroundTruth AI
          </div>
          <h2 className="h1" style={{ marginTop: 18 }}>
            Stop trusting resumes.
            <br />
            Start <span className="serif">verifying code.</span>
          </h2>
          <p className="lead">Replace keyword-matched claims with traceable proof of real engineering skill.</p>
        </Reveal>
        <Reveal delay={160}>
          <a className="btn" href="#profile" style={{ fontSize: 16, padding: "16px 30px" }}>
            See a Sample Evidence Profile <ArrowRight size={18} />
          </a>
        </Reveal>
      </div>
    </section>
  );
}
