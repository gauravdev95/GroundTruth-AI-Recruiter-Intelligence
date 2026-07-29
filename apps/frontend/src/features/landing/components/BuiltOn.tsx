import { TECH_STACK } from "../data/techStack";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

export function BuiltOn() {
  return (
    <section className="sec-tight sec" style={{ paddingBottom: 0 }}>
      <div className="wrap">
        <SectionHead
          eyebrow="Built on"
          title={
            <>
              A stack chosen for <span className="serif">verifiability.</span>
            </>
          }
        />
        <div className="badges">
          {TECH_STACK.map((b, i) => (
            <Reveal key={b.t} delay={i * 70}>
              <span className="badge">
                <b.I size={16} /> {b.t}
              </span>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
