import type { ReactNode } from "react";

import { Reveal } from "./Reveal";

interface SectionHeadProps {
  eyebrow: string;
  title: ReactNode;
  lead?: string;
  center?: boolean;
}

/** Standard eyebrow + heading + lead paragraph used at the top of each section. */
export function SectionHead({ eyebrow, title, lead, center }: SectionHeadProps) {
  return (
    <Reveal style={center ? { textAlign: "center" } : undefined}>
      <div className="eyebrow" style={center ? { justifyContent: "center" } : undefined}>
        {eyebrow}
      </div>
      <h2 className="h2">{title}</h2>
      {lead && (
        <p className="lead" style={center ? { margin: "0 auto" } : undefined}>
          {lead}
        </p>
      )}
    </Reveal>
  );
}
