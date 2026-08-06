import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

import { DURATION, EASE, useReducedMotionSafe } from "@/design/motion";
import { cn } from "@/lib/utils";

import { FAQ } from "../content/landing";
import { stagger } from "../lib/reveal";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";
import { SectionHead } from "./ui/SectionHead";

/**
 * One question and its answer.
 *
 * Built from a `<button>` and a panel rather than `<details>/<summary>`, for
 * one reason: `<details>` cannot animate its own disclosure, and browsers
 * disagree on whether `summary` is exposed as a button at all. The trade is
 * that the open state, the labelling and the chevron are this component's job,
 * which is what the three ARIA attributes below are doing.
 *
 * Height is animated here. That is one of the two declared exceptions to the
 * product's transform-and-opacity rule (see `design/motion.ts`): a disclosure
 * has to push the items below it down, and no transform does that.
 */
function Item({ question, answer, index }: { question: string; answer: string; index: number }) {
  const [open, setOpen] = useState(false);
  const reduced = useReducedMotionSafe();
  const id = useId();
  const panelId = `${id}-panel`;
  const buttonId = `${id}-button`;

  return (
    <Reveal as="li" delay={stagger(index, 0.05)} className="border-b border-black/10">
      <h3>
        <button
          id={buttonId}
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls={panelId}
          className="flex w-full items-center justify-between gap-6 py-6 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-paper"
        >
          <span className="font-sans text-gt-body font-medium text-gt-void">{question}</span>
          <ChevronDown
            aria-hidden="true"
            size={20}
            className={cn(
              "shrink-0 text-gt-slate transition-transform duration-200 ease-out",
              open && "rotate-180",
            )}
          />
        </button>
      </h3>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={panelId}
            role="region"
            aria-labelledby={buttonId}
            initial={reduced ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: DURATION.base, ease: EASE.standard }}
            className="overflow-hidden"
          >
            <p className="pb-6 pr-10 font-sans text-gt-body-sm leading-[1.7] text-gt-slate">
              {answer}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </Reveal>
  );
}

export function Faq() {
  return (
    <Section id="faq" label="Frequently asked questions" tone="paper">
      <div className="mx-auto max-w-[800px]">
        <SectionHead overline={FAQ.overline} headline={FAQ.headline} tone="light" size="h3" />

        <ul className="mt-16 border-t border-black/10">
          {FAQ.items.map((item, index) => (
            <Item key={item.question} index={index} {...item} />
          ))}
        </ul>
      </div>
    </Section>
  );
}
