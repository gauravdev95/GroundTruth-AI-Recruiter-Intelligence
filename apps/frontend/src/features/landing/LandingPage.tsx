import "./styles/landing.css";

import { Suspense, lazy, useEffect, useState } from "react";

import { Backdrop } from "./components/Backdrop";
import { Hero } from "./components/Hero";
import { Nav } from "./components/Nav";

/**
 * True once the below-fold sections should actually be built.
 *
 * Code-splitting them was not enough on its own. The cost was never downloading
 * twelve sections — it was constructing and laying them out inside the window
 * that decides LCP and Total Blocking Time, and none of them are on screen
 * while that happens.
 *
 * So the render waits for whichever comes first: the browser going idle, or the
 * reader doing anything that suggests they are heading down the page. The idle
 * timeout guarantees the content exists within 1.5s either way, so a crawler or
 * a reader who never interacts still gets the whole page.
 */
function useDeferredBelowFold(): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const supportsIdle = typeof requestIdleCallback === "function";

    const reveal = () => {
      setReady(true);
      teardown();
    };

    const teardown = () => {
      window.removeEventListener("scroll", reveal);
      window.removeEventListener("pointerdown", reveal);
      window.removeEventListener("keydown", reveal);
      if (supportsIdle) cancelIdleCallback(idleHandle);
      else clearTimeout(idleHandle);
    };

    window.addEventListener("scroll", reveal, { passive: true });
    window.addEventListener("pointerdown", reveal);
    window.addEventListener("keydown", reveal);

    const idleHandle = supportsIdle
      ? requestIdleCallback(reveal, { timeout: 1500 })
      : window.setTimeout(reveal, 1200);

    return teardown;
  }, []);

  return ready;
}

/**
 * The first commit is the backdrop, the navbar and the hero — which is all the
 * reader can see — and the remaining twelve sections arrive immediately
 * afterwards, off the critical path.
 *
 * Framer Motion is the only animation library on this page. GSAP, ScrollTrigger
 * and Lenis were removed and must not come back: two libraries contending for
 * the same `transform` is a correctness bug before it is a bundle-size one, and
 * Lenis' wheel smoothing is scroll-jacking with a softer name.
 */
const BelowFold = lazy(() => import("./BelowFold"));

export function LandingPage() {
  const showBelowFold = useDeferredBelowFold();

  return (
    <div className="gt">
      {/* First stop on the keyboard path, and it lands clear of the fixed nav. */}
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <Backdrop />
      <Nav />
      <Hero />

      {showBelowFold && (
        <Suspense fallback={null}>
          <BelowFold />
        </Suspense>
      )}
    </div>
  );
}
