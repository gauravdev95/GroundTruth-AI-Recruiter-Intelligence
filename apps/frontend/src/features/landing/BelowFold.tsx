import { Difference } from "./components/Difference";
import { Faq } from "./components/Faq";
import { FinalCta } from "./components/FinalCta";
import { Footer } from "./components/Footer";
import { ForEngineers } from "./components/ForEngineers";
import { ForRecruiters } from "./components/ForRecruiters";
import { HowItWorks } from "./components/HowItWorks";
import { Preview } from "./components/Preview";
import { Pricing } from "./components/Pricing";
import { Problem } from "./components/Problem";
import { Proof } from "./components/Proof";
import { Team } from "./components/Team";
import { Trust } from "./components/Trust";
import { ToneShift } from "./components/ui/ToneShift";

/**
 * Everything under the hero, in one lazily-loaded chunk.
 *
 * The page's rhythm is the alternation of `void` and `paper` sections, and it
 * is the reason nothing here needs a divider between sections. Reordering these
 * therefore is not free — two adjacent sections of the same tone read as one
 * very long section, which is the failure this arrangement exists to avoid.
 * `Preview` is the single gradient break, placed to land near the middle.
 */
export default function BelowFold() {
  return (
    <main id="main">
      <Proof />
      {/* First soft crossing: out of the hero's black world into the argument. */}
      <ToneShift direction="toLight" />
      <Problem />
      <HowItWorks />
      <ForEngineers />
      {/*
        Second soft crossing, and the other place it is earned — the two
        audience sections are the longest opposite-tone blocks on the page and
        sit back to back, so the cut between them was the most abrupt edge in
        the whole scroll. Every other boundary stays hard on purpose.
      */}
      <ToneShift direction="toDark" />
      <ForRecruiters />
      <Difference />
      <Preview />
      <Trust />

      {/* TODO: Add testimonials section once real customers are live */}

      <Pricing />
      <Faq />
      {/*
        The one place two `paper` sections sit together, which is why `Team`
        carries a top hairline that no other section needs. Making it `void`
        instead would have put it against the equally dark final CTA, and two
        black sections in a row is the failure this alternation exists to
        prevent — a rule between two white ones is the cheaper compromise.
      */}
      <Team />
      <FinalCta />
      <Footer />
    </main>
  );
}
