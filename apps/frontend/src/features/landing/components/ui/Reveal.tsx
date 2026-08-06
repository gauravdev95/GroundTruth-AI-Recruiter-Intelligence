import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { useReveal } from "../../lib/reveal";

/**
 * A single revealed block. `delay` staggers it behind its siblings.
 *
 * The animation itself lives in `lib/reveal.ts` — this is only the element it
 * gets applied to.
 */
export function Reveal({
  children,
  delay = 0,
  className,
  as = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  /** `li` where the parent is a list, so the reveal does not break semantics. */
  as?: "div" | "li";
}) {
  // The intersection satisfies both `motion.div` and `motion.li`, whose ref
  // types are otherwise incompatible. Nothing here reads an element-specific
  // property — the ref is only ever handed to the intersection observer.
  const reveal = useReveal<HTMLDivElement & HTMLLIElement>(delay);

  if (as === "li") {
    return (
      <motion.li {...reveal} className={className}>
        {children}
      </motion.li>
    );
  }

  return (
    <motion.div {...reveal} className={className}>
      {children}
    </motion.div>
  );
}
