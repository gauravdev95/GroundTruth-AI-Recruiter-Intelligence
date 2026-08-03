import type { ReactNode } from "react";

import { Reveal } from "./Reveal";

interface SectionHeadProps {
  /** The inspection gutter's address for this block — `§03 / VERIFICATION`. */
  coord: string;
  eyebrow: string;
  title: ReactNode;
  lead?: string;
  /** A disclosure line, rendered in mono beneath the lead. */
  note?: string;
}

/**
 * The one heading block every section on this page uses.
 *
 * Order is fixed — coordinate, eyebrow, h2, lead, note — and no section is
 * allowed its own variation. That uniformity is what lets the page carry
 * thirteen sections without a single divider graphic or background switch:
 * the reader learns the shape once, and the top hairline plus this block is
 * the only signal a new section has started.
 */
export function SectionHead({ coord, eyebrow, title, lead, note }: SectionHeadProps) {
  return (
    <Reveal className="sec-head">
      <p className="coord mono">{coord}</p>
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="h2">{title}</h2>
      {lead && <p className="lead">{lead}</p>}
      {note && <p className="sec-note">{note}</p>}
    </Reveal>
  );
}
