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
    <div className="space-y-4">
      <Link to="/recruiter/jobs" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink">
        <ArrowLeft size={14} aria-hidden="true" /> Back to jobs
      </Link>
      <EvidenceCard candidateProfileId={candidateProfileId} />
    </div>
  );
}
