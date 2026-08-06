import { FOOTER } from "../content/landing";
import { Container } from "./ui/Container";

/**
 * The footer.
 *
 * Three columns and no social row. Every link resolves — to an anchor on this
 * page, or to a route the application actually serves. Nothing points at `#`.
 *
 * That rule is why adding the Legal column meant adding four routes rather than
 * four hrefs: this footer sits three sections under a promise of full audit
 * trails and candidate appeal rights, and "Bias Audit Reports → #" would
 * undercut that promise more than a missing column ever could. Those routes
 * currently serve an honest placeholder; see `features/legal`.
 */
export function Footer() {
  return (
    <footer aria-label="Site footer" className="bg-gt-deeper py-20">
      <Container>
        <div className="flex items-start justify-between gap-8">
          <a
            href="#top"
            className="inline-flex items-center gap-2.5 rounded-sm font-grotesk text-xl font-bold tracking-tight text-gt-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-deeper"
          >
            <span aria-hidden="true" className="h-2 w-2 rounded-full bg-gt-electric" />
            GroundTruth
          </a>

          <a
            href="#top"
            className="group rounded-sm font-sans text-sm text-gt-dim transition-colors duration-200 hover:text-gt-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-deeper"
          >
            <span
              aria-hidden="true"
              className="inline-block transition-transform duration-200 group-hover:-translate-y-0.5"
            >
              ↑
            </span>{" "}
            {FOOTER.backToTop}
          </a>
        </div>

        <div className="mt-12 grid gap-12 sm:grid-cols-2 lg:max-w-[840px] lg:grid-cols-3">
          {FOOTER.columns.map((column) => (
            <nav key={column.heading} aria-label={column.heading}>
              <h2 className="font-sans text-sm uppercase tracking-wider text-gt-dim">
                {column.heading}
              </h2>
              <ul className="mt-5 space-y-3">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <a
                      href={link.href}
                      className="rounded-sm font-sans text-[15px] text-gt-ash transition-colors duration-200 hover:text-gt-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-deeper"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-16 flex flex-col gap-3 border-t border-white/10 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-sans text-sm text-gt-dim">{FOOTER.legal}</p>
          {/* The fourth and last surface carrying the sample-data disclosure. */}
          <p className="font-sans text-sm text-gt-dim">{FOOTER.disclosure}</p>
        </div>
      </Container>
    </footer>
  );
}
