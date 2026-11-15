import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EvidenceCard } from "../components/EvidenceCard";

/** Standalone evidence view for a candidate who is only "matched" so far —
 * no `Application` exists yet, so there's nothing to transition/message/
 * note about; that surface lives on `pipeline/pages/ApplicationDetailPage`
 * once the candidate actually applies. */
export function CandidateEvidencePage() {
  const { candidateProfileId } = useParams<{ candidateProfileId: string }>();
  if (!candidateProfileId) return null;

  return (
    <div className="space-y-6">
      <Link to="/recruiter/jobs" className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] transition hover:text-[var(--ink)]">
        <ArrowLeft size={14} aria-hidden="true" /> Back to jobs
      </Link>

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">
          Candidate evidence
        </h1>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[var(--slate)]">
          Everything GroundTruth has independently checked about this candidate — verified
          repositories, coding accounts, certificates and code-grounded interviews — read from
          their stored verification records. Nothing here is narrated or estimated.
        </p>
      </header>

      <EvidenceCard candidateProfileId={candidateProfileId} />
    </div>
  );
}
