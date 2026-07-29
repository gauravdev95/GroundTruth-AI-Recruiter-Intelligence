import { ArrowRight, Sparkles } from "lucide-react";

import { RECRUITER_STEPS } from "../data/recruiterSteps";
import { SAMPLE_CANDIDATES } from "../data/sampleCandidates";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function Recruiter() {
  return (
    <section
      className="sec"
      id="recruiter"
      style={{ background: "var(--ink-2)", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}
    >
      <div className="wrap">
        <SectionHead
          eyebrow="Recruiter workflow"
          title={
            <>
              From job description to a <span className="serif">ranked shortlist.</span>
            </>
          }
          lead="Recruiters review and approve every extracted requirement before search runs — the AI assists, the human decides."
        />
        <div className="rsteps">
          {RECRUITER_STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 80}>
              <div className="glass rstep">
                <span className="node-n">{s.n}</span>
                <s.I size={18} className="node-ic" style={{ color: "var(--a1)" }} />
                <h4>{s.t}</h4>
                <span>{s.s}</span>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={160}>
          <div className="glass table-card" id="profile">
            <div className="tbl-head">
              <b>Ranked candidates — Backend Engineer</b>
              <span className="pill sample">
                <Sparkles size={12} /> Sample / demo data
              </span>
            </div>
            <div className="rank-wrap">
              <table className="rank">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Similarity</th>
                    <th>Strong evidence</th>
                    <th>Evidence trail</th>
                  </tr>
                </thead>
                <tbody>
                  {SAMPLE_CANDIDATES.map((r) => (
                    <tr key={r.i}>
                      <td>
                        <span className="cand">
                          <span className="ava">{r.i}</span>
                          {r.n}
                        </span>
                      </td>
                      <td>
                        <span className="score">
                          <b>{r.sc.toFixed(2)}</b>
                          <span className="bar">
                            <i style={{ width: `${r.sc * 100}%` }} />
                          </span>
                        </span>
                      </td>
                      <td>
                        {r.sk.map((s) => (
                          <span key={s} className="skill">
                            {s}
                          </span>
                        ))}
                      </td>
                      <td>
                        <a className="ev-link" href="#explain">
                          {r.ev} linked commits <ArrowRight size={13} />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
