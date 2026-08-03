import { Link } from "react-router-dom";

import { FOOTER } from "../content/landing";

/**
 * The footer.
 *
 * Every link resolves — to a section id on this page, or to a route that exists
 * in `App.tsx`. There is no Blog, Changelog, Status, API or social row, and no
 * Privacy, Terms, About or Contact link, because none of those pages exist. A
 * footer full of dead links is the cheapest possible way to look unfinished,
 * and it is a particularly bad way to end a page whose argument is that claims
 * should be checkable.
 *
 * The final line is the third and last sample-data disclosure on the page —
 * hero console, §03 evidence panel, here. Repeated on every surface it would
 * read as defensive; in these three places it reads as a product that discloses
 * its own demo without being asked.
 */
export function Footer() {
  return (
    <footer className="foot">
      <div className="wrap">
        <div className="foot-top">
          <div className="foot-brand">
            <p className="foot-wordmark">{FOOTER.wordmark}</p>
            <p className="foot-blurb">{FOOTER.blurb}</p>
          </div>

          {FOOTER.columns.map((column) => (
            <div key={column.title}>
              <p className="foot-col-title">{column.title}</p>
              <div className="foot-links">
                {column.links.map((link) =>
                  /*
                    A router `<Link>` for real routes and a plain anchor for
                    in-page hashes. `<Link to="#access">` would push a history
                    entry for a scroll, and `<a href="/signup">` would force a
                    full document reload out of an SPA.
                  */
                  "route" in link && link.route ? (
                    <Link key={link.label} to={link.href}>
                      {link.label}
                    </Link>
                  ) : (
                    <a key={link.label} href={link.href}>
                      {link.label}
                    </a>
                  ),
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="foot-bottom">
          <span>{FOOTER.copyright}</span>
          <span className="foot-disclosure">{FOOTER.disclosure}</span>
        </div>
      </div>
    </footer>
  );
}
