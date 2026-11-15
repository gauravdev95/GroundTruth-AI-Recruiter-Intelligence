import { useEffect } from "react";
import { Link } from "react-router-dom";

/**
 * The landing page's four legal destinations, before those documents exist.
 *
 * WHY THIS IS A PLACEHOLDER AND NOT THE DOCUMENT.
 *
 * A privacy policy, a terms of service, a DPDP compliance statement and a bias
 * audit report are legal instruments. Publishing drafted-sounding text under
 * those four headings would be making binding representations about how a real
 * company handles real candidates' personal data, and about audits that have
 * not been run — on a product whose entire argument is that claims should be
 * checkable. Plausible filler is worse here than an honest gap, so none was
 * written.
 *
 * WHY THE ROUTES EXIST ANYWAY. The footer links to all four. Without these the
 * app has no catch-all route, so each link rendered a blank white page — which
 * is the one outcome worse than either a real document or an honest notice.
 *
 * REPLACING THIS: drop the real copy in per route and delete the component.
 * Nothing else imports it.
 *
 * PHASE 9 DECISION — LANDING TOKENS, DELIBERATELY. These are public pages
 * reached from the landing footer, with no authenticated chrome, no status
 * badges and no machine-extracted text — nothing on them is load-bearing for
 * the app token system, and moving them onto it would break the visitor's
 * visual continuity at exactly the moment they follow a footer link. So all
 * four pages stay in the landing `gt-*` system, polished consistently: same
 * layout, same contents navigation, same status callout on every page. Do
 * not mix app tokens in here.
 */
export function LegalDocumentPage({ title, summary }: { title: string; summary: string }) {
  useEffect(() => {
    const previous = document.title;
    document.title = `${title} — GroundTruth`;
    return () => {
      document.title = previous;
    };
  }, [title]);

  return (
    <main className="min-h-screen bg-gt-void px-6 py-16 text-gt-chalk sm:px-8 sm:py-24">
      <div className="mx-auto max-w-[680px]">
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-sm font-sans text-sm text-gt-ash transition-colors duration-200 hover:text-gt-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-void"
        >
          <span aria-hidden="true">←</span> Back to GroundTruth
        </Link>

        <p className="mt-12 font-sans text-gt-over uppercase text-gt-dim">Legal · GroundTruth</p>

        <h1 className="mt-4 font-grotesk text-gt-h3 font-bold text-gt-chalk">{title}</h1>

        <p className="mt-6 font-sans text-gt-body leading-relaxed text-gt-ash">{summary}</p>

        {/*
          The four documents, in the footer's order, with the current page
          marked — the contents navigation for a section whose documents do
          not exist yet. No sections to list inside a placeholder, so the
          honest table of contents is the section itself.
        */}
        <nav aria-label="Legal documents" className="mt-10 border-y border-white/10 py-6">
          <p className="font-sans text-gt-over uppercase text-gt-dim">In this section</p>
          <ul className="mt-4 space-y-3">
            {LEGAL_DOCUMENTS.map((doc) => {
              const current = doc.title === title;
              return (
                <li key={doc.href}>
                  {current ? (
                    <span
                      aria-current="page"
                      className="inline-flex items-center gap-2 font-sans text-[15px] font-medium text-gt-chalk"
                    >
                      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-gt-electric" />
                      {doc.title}
                    </span>
                  ) : (
                    <Link
                      to={doc.href}
                      className="rounded-sm font-sans text-[15px] text-gt-ash transition-colors duration-200 hover:text-gt-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-void"
                    >
                      {doc.title}
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>

        {/*
          The status of the document, set apart from the summary so a reader
          cannot mistake the notice for the document itself. Copy verbatim
          from the pre-Phase 9 placeholder.
        */}
        <section
          aria-label="Document status"
          className="mt-10 rounded-lg border border-white/10 bg-white/[0.03] p-6"
        >
          <p className="font-sans text-gt-over uppercase text-gt-dim">Document status</p>
          <p className="mt-4 font-sans text-gt-body-sm leading-relaxed text-gt-ash">
            This document is being prepared ahead of public launch and is not published yet. We would
            rather leave it blank than post a draft that reads as a commitment we have not made. If
            you need it before then — as a candidate, a customer, or a regulator — write to us and we
            will share the current position directly.
          </p>
        </section>

        <p className="mt-10 border-t border-white/10 pt-8 font-sans text-sm text-gt-dim">
          Last updated: not yet published.
        </p>
      </div>
    </main>
  );
}

/** The four legal routes, in the landing footer's order. */
const LEGAL_DOCUMENTS = [
  { href: "/privacy", title: "Privacy Policy" },
  { href: "/terms", title: "Terms of Service" },
  { href: "/dpdp", title: "DPDP Compliance" },
  { href: "/bias-audit", title: "Bias Audit Reports" },
];
