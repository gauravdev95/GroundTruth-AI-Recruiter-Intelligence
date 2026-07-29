import { useEffect, useState } from "react";

import { useInView } from "@/hooks/useInView";

interface CountUpProps {
  to: number;
  duration?: number;
  suffix?: string;
}

/** Animates from 0 up to a target number once it scrolls into view. */
export function CountUp({ to, duration = 1100, suffix = "" }: CountUpProps) {
  const [ref, inView] = useInView(0.4);
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!inView) return;

    let frame: number;
    const start = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      setValue(Math.round((1 - Math.pow(1 - progress, 3)) * to));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [inView, to, duration]);

  return (
    <span ref={ref}>
      {value}
      {suffix}
    </span>
  );
}
