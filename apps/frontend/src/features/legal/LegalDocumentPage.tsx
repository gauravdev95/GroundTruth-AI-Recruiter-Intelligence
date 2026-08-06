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
    <main className="min-h-screen bg-gt-void px-6 py-24 text-gt-chalk sm:px-8">
      <div className="mx-auto max-w-[680px]">
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-sm font-sans text-sm text-gt-ash transition-colors duration-200 hover:text-gt-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4 focus-visible:ring-offset-gt-void"
        >
          <span aria-hidden="true">←</span> Back to GroundTruth
        </Link>

        <h1 className="mt-12 font-grotesk text-gt-h3 font-bold text-gt-chalk">{title}</h1>

        <p className="mt-6 font-sans text-gt-body leading-relaxed text-gt-ash">{summary}</p>

        <p className="mt-6 font-sans text-gt-body-sm leading-relaxed text-gt-ash">
          This document is being prepared ahead of public launch and is not published yet. We would
          rather leave it blank than post a draft that reads as a commitment we have not made. If
          you need it before then — as a candidate, a customer, or a regulator — write to us and we
          will share the current position directly.
        </p>

        <p className="mt-10 border-t border-white/10 pt-8 font-sans text-sm text-gt-dim">
          Last updated: not yet published.
        </p>
      </div>
    </main>
  );
}
