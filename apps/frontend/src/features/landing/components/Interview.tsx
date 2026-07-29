import { ArrowUpDown, Check, GitCommitHorizontal, ScanSearch, ShieldCheck, Sparkles } from "lucide-react";

import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function Interview() {
  return (
    <section className="sec" id="product">
      <div className="wrap iv">
        <div>
          <SectionHead
            eyebrow="The differentiator"
            title={
              <>
                An interview grounded in <span className="serif">their own code.</span>
              </>
            }
            lead="Not a question bank. Every prompt is generated from the candidate's actual repositories — and every answer is checked back against them."
          />
          <div className="iv-points">
            <Reveal delay={80}>
              <div className="iv-point">
                <span className="iv-ic">
                  <GitCommitHorizontal size={18} />
                </span>
                <div>
                  <h4>Generated from real commits</h4>
                  <p>Questions reference specific files, diffs, and design decisions the candidate actually made.</p>
                </div>
              </div>
            </Reveal>
            <Reveal delay={170}>
              <div className="iv-point">
                <span className="iv-ic">
                  <ArrowUpDown size={18} />
                </span>
                <div>
                  <h4>Adapts in real time</h4>
                  <p>Strong answers pull deeper follow-ups; vague or inconsistent ones get probed immediately.</p>
                </div>
              </div>
            </Reveal>
            <Reveal delay={260}>
              <div className="iv-point">
                <span className="iv-ic">
                  <ShieldCheck size={18} />
                </span>
                <div>
                  <h4>Verified against the repository</h4>
                  <p>Every claim in an answer is cross-checked with what the code and history actually show.</p>
                </div>
              </div>
            </Reveal>
          </div>
        </div>

        <Reveal delay={140}>
          <div className="glass chat">
            <div className="chat-head">
              <b>Adaptive Interview — session</b>
              <span className="pill sample">
                <Sparkles size={12} /> Sample / demo data
              </span>
            </div>
            <div className="chat-body">
              <div className="bub ai">
                In commit <span className="mono">a3f9e21</span> you moved payment retries into a
                background worker in <span className="mono">tasks/retry.py</span>. Why exponential
                backoff instead of a fixed delay?
              </div>
              <div className="bub me">
                Fixed delays were hammering the gateway during outages. Backoff with jitter spreads
                retries out, and idempotency keys keep repeated attempts safe.
              </div>
              <span className="chk ok">
                <Check size={12} /> Checked against repository — consistent
              </span>
              <div className="bub ai">
                You mentioned idempotency keys — but <span className="mono">retry.py</span> doesn't
                guard against duplicate charges if the worker restarts mid-task. Walk me through
                what happens in that case.
              </div>
              <span className="chk probe">
                <ScanSearch size={12} /> Adaptive follow-up — probing inconsistency
              </span>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
