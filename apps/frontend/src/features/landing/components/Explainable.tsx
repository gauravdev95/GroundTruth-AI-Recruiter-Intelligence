import { ArrowDown, Check, Cpu, GitBranch, Lock } from "lucide-react";

import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function Explainable() {
  return (
    <section className="sec" id="explain">
      <div className="wrap">
        <SectionHead
          eyebrow="Trust by design"
          title={
            <>
              Explainable, <span className="serif">not a black box.</span>
            </>
          }
          lead="No opaque scores. Every rank on the shortlist expands into evidence you can open, read, and challenge."
        />
        <div className="xp">
          <Reveal delay={60}>
            <div className="glass xp-card" style={{ height: "100%" }}>
              <h3>Every rank is traceable</h3>
              <p>
                A similarity score is never the end of the story. Each ranked candidate links back
                to the exact files, commits, and interview answers that produced it.
              </p>
              <div className="trace">
                <div>
                  <span className="hl">rank #1</span> · Ananya Sharma · 0.94
                </div>
                <div>└─ skill: FastAPI — <span className="hl">Strong Evidence</span></div>
                <div>&nbsp;&nbsp;&nbsp;├─ api/routes/payments.py · commit a3f9e21</div>
                <div>&nbsp;&nbsp;&nbsp;├─ 2 more repositories · 12 linked commits</div>
                <div>&nbsp;&nbsp;&nbsp;└─ interview Q4 — consistent ✓</div>
              </div>
              <div className="xp-chips">
                <span className="pill">
                  <Check size={12} /> Visible evidence links
                </span>
                <span className="pill">
                  <Check size={12} /> Challengeable results
                </span>
              </div>
            </div>
          </Reveal>
          <Reveal delay={170}>
            <div className="glass xp-card" style={{ height: "100%" }}>
              <h3>Two-stage repository analysis</h3>
              <p>
                Deterministic static tools run first across the whole repository. The LLM only ever
                sees a small set of high-value files — a cost, privacy, and trust decision.
              </p>
              <div className="stage2">
                <div className="s2-row">
                  <span className="s2-ic">
                    <GitBranch size={16} />
                  </span>
                  <div>
                    <b style={{ fontSize: 13.5 }}>Stage 1 — Static analysis</b>
                    <div className="mono">TREE-SITTER / AST · DETERMINISTIC · FULL REPO</div>
                  </div>
                </div>
                <span className="s2-arrow">
                  <ArrowDown size={15} />
                </span>
                <div className="s2-row">
                  <span className="s2-ic">
                    <Cpu size={16} />
                  </span>
                  <div>
                    <b style={{ fontSize: 13.5 }}>Stage 2 — LLM deep read</b>
                    <div className="mono">HIGH-VALUE FILES ONLY · NEVER THE FULL REPO</div>
                  </div>
                </div>
              </div>
              <div className="xp-chips">
                <span className="pill">
                  <Lock size={12} /> Full repo never sent to the AI
                </span>
                <span className="pill">
                  <Check size={12} /> Lower inference cost
                </span>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
