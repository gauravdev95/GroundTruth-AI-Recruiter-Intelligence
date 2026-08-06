import "./styles/landing.css";

import { Suspense, lazy, useEffect, useState } from "react";

import { NAV } from "./content/landing";
import { Hero } from "./components/Hero";
import { Nav } from "./components/Nav";

/**
 * True once the below-fold sections should actually be built.
 *
 * Code-splitting them is not enough on its own. The cost was never downloading
 * twelve sections — it is constructing and laying them out inside the window
 * that decides Largest Contentful Paint and Total Blocking Time, while none of
 * them are on screen.
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

const BelowFold = lazy(() => import("./BelowFold"));

/**
 * The GroundTruth landing page.
 *
 * First commit is the nav and the hero — all the reader can see — with the
 * remaining twelve sections arriving immediately afterwards, off the critical
 * path.
 *
 * Framer Motion is the only animation library here, and the scroll reveals run
 * on the shared observer registry in `design/motion.ts` rather than on Framer's
 * `whileInView`. The hero's constellation is hand-drawn to a 2D canvas: see the
 * note at the top of `components/SkillConstellation.tsx` for why there is no 3D
 * engine in this bundle.
 */
export function LandingPage() {
  const showBelowFold = useDeferredBelowFold();

  return (
    <div className="bg-gt-void">
      {/* First stop on the keyboard path, and it lands clear of the fixed nav. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-6 focus:top-6 focus:z-[60] focus:rounded-lg focus:bg-gt-electric focus:px-5 focus:py-3 focus:font-sans focus:text-sm focus:font-medium focus:text-white"
      >
        {NAV.skipToContent}
      </a>

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
