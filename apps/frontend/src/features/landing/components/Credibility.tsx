import { FileCode2, Trophy } from "lucide-react";

import { TEAM_MEMBERS } from "../data/teamMembers";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function Credibility() {
  return (
    <section className="sec" id="team">
      <div className="wrap">
        <SectionHead
          eyebrow="The team"
          title={
            <>
              Built by four engineers who <span className="serif">read the code.</span>
            </>
          }
        />
        <div className="cred">
          <Reveal delay={0}>
            <span className="pill">
              <Trophy size={13} /> Top 3 — Smart India Hackathon 2025
            </span>
          </Reveal>
          <Reveal delay={90}>
            <span className="pill">
              <FileCode2 size={13} /> Final-year B.Tech CSE capstone · 2026–27
            </span>
          </Reveal>
        </div>
        <div className="team">
          {TEAM_MEMBERS.map((m, i) => (
            <Reveal key={m.i} delay={i * 90}>
              <div className="glass member">
                <span className="ava">{m.i}</span>
                <div>
                  <b>{m.n}</b>
                  <div>
                    <span>{m.r}</span>
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
