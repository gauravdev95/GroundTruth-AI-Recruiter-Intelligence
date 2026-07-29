import { useEffect, useRef, useState } from "react";

/**
 * Tracks whether an element has scrolled into the viewport at least once.
 * Stops observing after the first intersection — used to drive one-shot
 * "reveal on scroll" animations rather than re-triggering on every pass.
 */
export function useInView<T extends HTMLElement = HTMLDivElement>(threshold = 0.16) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return [ref, inView] as const;
}
