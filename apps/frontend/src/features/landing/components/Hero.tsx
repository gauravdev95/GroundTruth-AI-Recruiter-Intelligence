import { CTA, HERO } from "../content/landing";
import { HeroConsole } from "./HeroConsole";
import { MagneticButton } from "./MagneticButton";

/**
 * §00 — the hero. The thesis stated on the left, performed on the right.
 *
 * Everything in the copy column is static at first paint and never animates:
 * coordinate, pill, H1, lead, both CTAs, capability strip. The H1 in particular
 * ships as markup in `index.html`, so the value proposition is readable before
 * a line of JavaScript has run — and the two accent words take their gradient
 * from CSS, not from an animation.
 *
 * That restraint is deliberate rather than lazy. A headline that fades in is a
 * headline that is briefly absent, and the ten-second window in which a
 * stranger decides what this product is starts at first paint, not at
 * hydration. The only thing that moves up here is the console, and it waits
 * for the browser to go idle before it starts.
 *
 * `min-height: 88vh` in the stylesheet, never 100vh — see the note there about
 * the illusion of completeness. Part of §01 has to break the fold, and that
 * overlap is the page's only scroll cue; there is no bouncing arrow.
 *
 * The copy column and the backdrop are mirrored verbatim in `index.html`. Any
 * change to this markup has to be made there too, or the static hero will flash
 * and be replaced by a subtly different one when React mounts.
 */
export function Hero() {
  return (
    <header className="hero" id="top">
      <div className="wrap hero-in">
        <div className="hero-copy">
          <p className="coord mono">{HERO.coord}</p>

          <p className="pill hero-pill">
            <span className="pill-mark" aria-hidden="true">
              ◈
            </span>
            {HERO.pill}
          </p>

          <h1 className="h1">
            {HERO.h1.before}
            <span className="accent">{HERO.h1.accentA}</span>
            {HERO.h1.middle}
            <span className="accent">{HERO.h1.accentB}</span>
            {HERO.h1.after}
          </h1>

          <p className="hero-lead">{HERO.lead}</p>

          {/*
            Two CTAs at equal visual weight. The second is the ghost variant
            rather than a smaller primary: it is a different kind of action, not
            a weaker one, and a recruiter arriving here must not feel the page
            has already chosen the student's path for them.
          */}
          <div className="hero-ctas">
            <MagneticButton to={CTA.student.href} arrow>
              {CTA.student.label}
            </MagneticButton>
            <MagneticButton href="#verification" variant="secondary">
              ▷ See how it works
            </MagneticButton>
          </div>

          {/*
            Capability facts, not vanity metrics. Every value is a property of
            the system — seven stages, a 1536-dimension vector — rather than a
            count of anything that has happened on it, which is the only kind of
            number a pre-launch product can honestly put above the fold.
          */}
          <dl className="hero-caps">
            {HERO.capabilities.map((cap) => (
              <div key={cap.label}>
                <dt className="hero-cap-value mono num">{cap.value}</dt>
                <dd className="hero-cap-label">{cap.label}</dd>
                {cap.detail && <dd className="hero-cap-detail mono">{cap.detail}</dd>}
              </div>
            ))}
          </dl>
        </div>

        <div className="hero-right">
          <HeroConsole />
        </div>
      </div>
    </header>
  );
}
