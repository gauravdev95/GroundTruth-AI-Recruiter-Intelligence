import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Overline } from "./Overline";
import { Reveal } from "./Reveal";

type Tone = "light" | "dark" | "wash";

/**
 * Overline, headline, optional lead — the opening of every section.
 *
 * A component rather than three lines repeated eleven times, because the
 * spacing between those three elements is the page's most repeated visual
 * relationship. When it is retyped per section it drifts by a few pixels each
 * time, and the drift is exactly the sort of thing that reads as "unfinished"
 * without a reader ever being able to say why.
 */
export function SectionHead({
  overline,
  headline,
  lead,
  tone,
  size = "h2",
  accentOverline = false,
  className,
}: {
  overline: string;
  headline: ReactNode;
  lead?: string;
  tone: Tone;
  /** `h3` is the quieter 48px scale used by Trust and the FAQ. */
  size?: "h2" | "h3";
  /** Electric overline. The brief specifies it on the two audience sections. */
  accentOverline?: boolean;
  className?: string;
}) {
  const overlineTone = accentOverline ? "accent" : tone === "wash" ? "wash" : tone;

  return (
    <div className={className}>
      <Reveal>
        <Overline tone={overlineTone}>{overline}</Overline>
      </Reveal>

      <Reveal delay={0.06}>
        <h2
          className={cn(
            "mt-5 max-w-[16ch] font-grotesk font-bold",
            size === "h2" ? "text-gt-h2" : "text-gt-h3",
            tone === "light" && "text-gt-void",
            tone === "dark" && "text-gt-chalk",
            tone === "wash" && "text-white",
          )}
        >
          {headline}
        </h2>
      </Reveal>

      {lead && (
        <Reveal delay={0.12}>
          <p
            className={cn(
              "mt-6 max-w-[720px] font-sans text-gt-body",
              tone === "light" && "text-gt-slate",
              tone === "dark" && "text-gt-ash",
              tone === "wash" && "text-white/80",
            )}
          >
            {lead}
          </p>
        </Reveal>
      )}
    </div>
  );
}

/**
 * The checkmark bullet list used by both audience sections.
 *
 * The tick is `aria-hidden` and the list is a real `<ul>`: the mark is a visual
 * restatement of "this is a list item", which a screen reader already announces.
 * Left unlabelled it would be read out as nothing; given a label it would be
 * read out twice.
 */
export function CheckList({ items, tone }: { items: readonly string[]; tone: Tone }) {
  return (
    <ul className="mt-8 space-y-4">
      {items.map((item, index) => (
        <Reveal as="li" key={item} delay={index * 0.05} className="flex items-start gap-3">
          <Check
            aria-hidden="true"
            size={20}
            strokeWidth={2.5}
            className="mt-0.5 shrink-0 text-gt-electric"
          />
          <span
            className={cn(
              "font-sans text-gt-body-sm",
              tone === "light" ? "text-gt-void" : "text-gt-chalk",
            )}
          >
            {item}
          </span>
        </Reveal>
      ))}
    </ul>
  );
}
