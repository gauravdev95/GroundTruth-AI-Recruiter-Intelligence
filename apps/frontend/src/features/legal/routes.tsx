import { lazy } from "react";
import { Route } from "react-router-dom";

/**
 * The four legal routes the landing footer links to.
 *
 * Code-split like every other non-landing route: nobody arriving at `/` needs
 * these, and one `<Suspense>` boundary in App.tsx already covers them.
 *
 * All four render the same placeholder with different headings. That is
 * deliberate and temporary — see the note in `LegalDocumentPage.tsx` for why no
 * legal text was drafted to fill them.
 */
const LegalDocumentPage = lazy(() =>
  import("./LegalDocumentPage").then((m) => ({ default: m.LegalDocumentPage })),
);

/** Spread directly inside the root <Routes> in App.tsx. */
export const legalRoutes = (
  <>
    <Route
      path="/privacy"
      element={
        <LegalDocumentPage
          title="Privacy Policy"
          summary="How GroundTruth collects, stores, processes and deletes your personal data, including the code and interview transcripts we analyse, and the rights you hold over all of it."
        />
      }
    />
    <Route
      path="/terms"
      element={
        <LegalDocumentPage
          title="Terms of Service"
          summary="The terms under which engineers and hiring teams use GroundTruth, including what we verify, what we do not, and what a verification result does and does not entitle either side to."
        />
      }
    />
    <Route
      path="/dpdp"
      element={
        <LegalDocumentPage
          title="DPDP Compliance"
          summary="Our position under India's Digital Personal Data Protection Act as a Data Fiduciary: lawful basis, consent and withdrawal, retention periods, cross-border transfer, and how to reach our grievance officer."
        />
      }
    />
    <Route
      path="/bias-audit"
      element={
        <LegalDocumentPage
          title="Bias Audit Reports"
          summary="Independent audits of our scoring and matching for disparate impact, published annually, alongside the methodology, the demographic categories tested, and every remediation made in response."
        />
      }
    />
  </>
);
