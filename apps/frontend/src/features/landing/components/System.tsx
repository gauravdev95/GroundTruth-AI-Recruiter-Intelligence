import { SYSTEM } from "../content/landing";
import { STAGGER } from "../lib/motion";
import { SectionHead } from "./SectionHead";
import { Stagger, StaggerItem } from "./Stagger";

/**
 * §10 — five layers, and what each one runs on.
 *
 * Every name in this section was read off `apps/frontend/package.json` and
 * `apps/backend/pyproject.toml`, which is what "listed from this repository,
 * not from a wish list" in the lead is promising. Three libraries the original
 * brief named are missing precisely because they are missing from the
 * repository — the reasoning is recorded on `SYSTEM` in `content/landing.ts`.
 * On a page whose thesis is that claims should be checkable, an architecture
 * diagram is the one place a reader can actually check one.
 *
 * Full 1240px content width, the same as every other section. A narrower
 * architecture block reads as an aside rather than as the stack the page has
 * been describing for ten sections.
 */
export function System() {
  return (
    <section className="sec" id="system">
      <div className="wrap">
        <SectionHead coord={SYSTEM.coord} eyebrow={SYSTEM.eyebrow} title={SYSTEM.h2} lead={SYSTEM.lead} />

        <Stagger className="layers" gap={STAGGER.siblings}>
          {SYSTEM.layers.map((layer) => (
            <StaggerItem className="layer" key={layer.layer}>
              <span className="layer-name">
                {/* Neutral node. A layer existing is not a verified claim. */}
                <span className="layer-node" aria-hidden="true" />
                {layer.layer}
              </span>

              <span className="layer-tech">
                {layer.tech.map((tech) => (
                  <span className="layer-chip" key={tech}>
                    {tech}
                  </span>
                ))}
              </span>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
