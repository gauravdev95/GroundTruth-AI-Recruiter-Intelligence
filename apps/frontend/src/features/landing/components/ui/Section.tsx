import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Container } from "./Container";

/**
 * `void` and `paper` alternate down the page — that alternation is the page's
 * rhythm and the reason it never needs a divider. `wash` is the single
 * gradient section; `deeper` is the footer alone.
 */
type Tone = "void" | "paper" | "deeper" | "wash";

interface SectionProps {
  /** Doubles as the anchor target for nav and footer links. */
  id: string;
  /** Names the section for assistive technology. Never rendered visually. */
  label: string;
  tone: Tone;
  children: ReactNode;
  className?: string;
  /** Thin strips (the social-proof line) opt out of the 120–160px rhythm. */
  padding?: "default" | "thin" | "tall";
  /** Sections that lay out their own container manage their own width. */
  bare?: boolean;
}

const TONE_CLASS: Record<Tone, string> = {
  void: "bg-gt-void text-gt-chalk",
  paper: "bg-gt-paper text-gt-void",
  deeper: "bg-gt-deeper text-gt-chalk",
  /* The one decorative gradient on the page. 135° so it runs corner to corner
     rather than reading as a horizontal band. */
  wash: "bg-[linear-gradient(135deg,#1E40FF_0%,#7C3AED_100%)] text-white",
};

const PADDING_CLASS = {
  default: "py-20 md:py-[120px] lg:py-[160px]",
  thin: "py-20",
  tall: "py-24 md:py-[160px] lg:py-[200px]",
} as const;

/**
 * Every section on the page below the hero.
 *
 * `scroll-mt-[72px]` is load-bearing rather than cosmetic: the nav is fixed at
 * 72px, so an anchor jump without it parks the section's headline underneath
 * the nav bar and the reader lands on a section that appears to start mid-copy.
 */
export function Section({
  id,
  label,
  tone,
  children,
  className,
  padding = "default",
  bare = false,
}: SectionProps) {
  return (
    <section
      id={id}
      aria-label={label}
      className={cn("scroll-mt-[72px]", TONE_CLASS[tone], PADDING_CLASS[padding], className)}
    >
      {bare ? children : <Container>{children}</Container>}
    </section>
  );
}
