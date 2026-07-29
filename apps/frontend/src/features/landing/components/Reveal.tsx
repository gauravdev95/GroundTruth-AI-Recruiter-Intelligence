import type { CSSProperties, ReactNode } from "react";

import { useInView } from "@/hooks/useInView";

interface RevealProps {
  children: ReactNode;
  delay?: number;
  className?: string;
  style?: CSSProperties;
}

/** Fades and lifts its content into place the first time it scrolls into view. */
export function Reveal({ children, delay = 0, className = "", style }: RevealProps) {
  const [ref, inView] = useInView();

  return (
    <div
      ref={ref}
      className={`rv ${inView ? "rv-in" : ""} ${className}`}
      style={{ transitionDelay: `${delay}ms`, ...style }}
    >
      {children}
    </div>
  );
}
