import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { QUESTIONS } from "../content/landing";
import { DURATION, EASE, useReducedMotionSafe } from "../lib/motion";
import { MagneticButton } from "./MagneticButton";
import { Reveal } from "./Reveal";
import { SectionHead } from "./SectionHead";

/**
 * §09 — what people ask first.
 *
 * The first item is open by default. A fully collapsed accordion is a section
 * with no visible content, which on a page where every other block is dense
 * reads as a rendering failure rather than as an invitation.
 *
 * The last question is the one that matters. "Is anything on this page real
 * data?" answered with "no, every figure is a sample run" is the strongest
 * trust signal available to a pre-launch verification product: it is the page
 * applying its own standard to itself, before a sceptical reader gets to.
 *
 * It ends on a CTA, like §07, because a reader who has just had their last
 * objection answered should not have to go looking for the button.
 */
export function Questions() {
  const [open, setOpen] = useState(0);

  return (
    <section className="sec" id="questions">
      <div className="wrap">
        <SectionHead coord={QUESTIONS.coord} eyebrow={QUESTIONS.eyebrow} title={QUESTIONS.h2} />

        <div className="faq">
          {QUESTIONS.items.map((item, index) => (
            <FaqItem
              key={item.q}
              item={item}
              open={open === index}
              onToggle={() => setOpen((current) => (current === index ? -1 : index))}
              id={`faq-${index}`}
            />
          ))}
        </div>

        <Reveal className="faq-cta">
          <MagneticButton to={QUESTIONS.cta.href} arrow>
            {QUESTIONS.cta.label}
          </MagneticButton>
        </Reveal>
      </div>
    </section>
  );
}

interface FaqItemProps {
  item: { q: string; a: string };
  open: boolean;
  onToggle: () => void;
  id: string;
}

/**
 * One question.
 *
 * The `+`/`−` sign is a text glyph rotated by transform rather than two swapped
 * icons, so the state change costs no repaint and reads as one control changing
 * rather than two controls alternating.
 *
 * The body animates `height`, the same declared exception as §03's stage
 * disclosures — a disclosure's job is to reflow what sits beneath it, and no
 * transform moves a sibling.
 */
function FaqItem({ item, open, onToggle, id }: FaqItemProps) {
  const reduced = useReducedMotionSafe();

  return (
    <div className="faq-item">
      <button type="button" className="faq-btn" aria-expanded={open} aria-controls={id} onClick={onToggle}>
        {item.q}
        <motion.span
          className="faq-sign"
          aria-hidden="true"
          animate={{ rotate: open ? 45 : 0 }}
          transition={{ duration: reduced ? 0 : DURATION.fast, ease: EASE.standard }}
        >
          +
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            className="faq-body"
            initial={reduced ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduced ? { height: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : DURATION.base, ease: EASE.entrance }}
          >
            <p className="faq-body-in">{item.a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
