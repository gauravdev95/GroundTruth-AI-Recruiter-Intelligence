import { Access } from "./components/Access";
import { Assessment } from "./components/Assessment";
import { Audience } from "./components/Audience";
import { Difference } from "./components/Difference";
import { Failure } from "./components/Failure";
import { Footer } from "./components/Footer";
import { Matching } from "./components/Matching";
import { Origin } from "./components/Origin";
import { Questions } from "./components/Questions";
import { Sources } from "./components/Sources";
import { Start } from "./components/Start";
import { System } from "./components/System";
import { Verification } from "./components/Verification";

/**
 * Everything below the fold, in one lazily-imported chunk.
 *
 * Twelve sections after the hero, and rendering all of them in the first commit
 * was the largest single contributor to Total Blocking Time — the cost is not
 * downloading them, it is constructing and laying them out inside the window
 * that decides LCP. None of it is on screen while that happens.
 *
 * Splitting here rather than per section is deliberate: twelve lazy boundaries
 * would mean twelve requests and twelve Suspense fallbacks to keep from
 * shifting layout, for chunks of a few kilobytes each. One boundary, loaded
 * immediately after the hero has painted, gets the whole benefit.
 *
 * Inserting this content cannot affect CLS: all of it lands below the viewport,
 * and layout shift is only counted for content the reader can see move.
 *
 * SECTION ORDER IS AN ARGUMENT, NOT A LIST
 *
 * Each section does one job, and no two do the same one — a page fails from
 * repetition, not from length. Three mechanism sections is the cap, and §03,
 * §04 and §05 are all three of them:
 *
 *   §01 failure      the problem
 *   §02 audience     the routing decision, before any mechanism
 *   §03 verification mechanism 1 — the pipeline and its artefact
 *   §04 assessment   mechanism 2 — the interview and its rubric
 *   §05 matching     mechanism 3 — one computation, both directions
 *   §06 difference   the payoff, stated plainly
 *   §07 access       the risk the page has been accumulating, answered
 *   §08 sources      provenance
 *   §09 questions    the remaining objections
 *   §10 system       the stack, checkable against this repository
 *   §11 origin       the reason, standing in for social proof
 *   §12 start        both audiences, one last time
 */
export default function BelowFold() {
  return (
    <>
      <main id="main">
        <Failure />
        <Audience />
        <Verification />
        <Assessment />
        <Matching />
        <Difference />
        <Access />
        <Sources />
        <Questions />
        <System />
        <Origin />
        <Start />
      </main>
      <Footer />
    </>
  );
}
