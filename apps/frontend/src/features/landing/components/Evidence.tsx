import { ShieldCheck } from "lucide-react";

import { EVIDENCE_LEVELS } from "../data/evidenceLevels";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function Evidence() {
  return (
    <section className="sec" id="evidence">
      <div className="wrap">
        <SectionHead
          eyebrow="Skill evidence levels"
          title={
            <>
              Every skill carries its <span className="serif">weight of proof.</span>
            </>
          }
          lead="Skills aren't binary tags. Each one is graded by how much verifiable evidence stands behind it."
        />
        <div className="bento">
          {EVIDENCE_LEVELS.map((l, i) => (
            <Reveal key={l.t} delay={i * 110}>
              <div className={`glass lv ${l.cls || ""}`}>
                <div className="lv-meter">
                  {[0, 1, 2, 3].map((j) => (
                    <i key={j} className={j < l.on ? "on" : ""} />
                  ))}
                </div>
                <span className="lv-tag">{l.tag}</span>
                <h3>{l.t}</h3>
                <p>{l.d}</p>
              </div>
            </Reveal>
          ))}
          <Reveal delay={340} style={{ gridColumn: "1 / -1" }}>
            <div className="glass lv lv4">
              <div className="lv-badge">
                <ShieldCheck size={44} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div className="lv-meter">
                  {[0, 1, 2, 3].map((j) => (
                    <i key={j} className="on" />
                  ))}
                </div>
                <span className="lv-tag">LEVEL 4 / 4</span>
                <h3>Strong Evidence</h3>
                <p style={{ maxWidth: 560 }}>
                  Verified across multiple projects — detected in code and defended in interview.
                  This is the signal a recruiter shortlists on.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
