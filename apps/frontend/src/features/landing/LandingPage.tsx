import "./styles/landing.css";

import { BuiltOn } from "./components/BuiltOn";
import { Credibility } from "./components/Credibility";
import { Evidence } from "./components/Evidence";
import { Explainable } from "./components/Explainable";
import { FinalCTA } from "./components/FinalCTA";
import { Footer } from "./components/Footer";
import { Hero } from "./components/Hero";
import { Interview } from "./components/Interview";
import { Nav } from "./components/Nav";
import { Pipeline } from "./components/Pipeline";
import { Problem } from "./components/Problem";
import { Recruiter } from "./components/Recruiter";

export function LandingPage() {
  return (
    <div className="gt">
      <Nav />
      <Hero />
      <main>
        <Problem />
        <Pipeline />
        <Interview />
        <Evidence />
        <Recruiter />
        <Explainable />
        <BuiltOn />
        <Credibility />
      </main>
      <FinalCTA />
      <Footer />
    </div>
  );
}
