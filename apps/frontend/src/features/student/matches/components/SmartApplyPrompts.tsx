import { Skeleton } from "@/components";
import { useMyApplications } from "@/features/student/applications/hooks/useApplications";

import { useJobFeed } from "../hooks/useJobFeed";
import { HighMatchCard } from "./HighMatchCard";

/**
 * Every Tier B match, above the ordinary feed.
 *
 * Renders nothing at all when there are none — deliberately, and against the
 * house rule that a section never shows a blank state. An empty
 * "recommendations" heading is not an empty state, it is a claim that this
 * student *should* have recommendations and does not, which is both untrue
 * (Tier B is relative to each job's pool, so having none is the normal case)
 * and discouraging. The job feed below is the honest home for "here is what
 * you matched"; this block only exists when there is something worth
 * interrupting for.
 */
export function SmartApplyPrompts() {
  const feed = useJobFeed();
  const applications = useMyApplications();

  if (feed.isPending) return <Skeleton className="h-52 w-full" />;
  if (feed.isError || !feed.data) return null;

  const recommended = feed.data.filter((match) => match.tier === "smart_apply_recommended");
  if (recommended.length === 0) return null;

  // One lookup for the whole list rather than a query per card. An applied
  // job still shows its card — with the button replaced by "Applied" — so the
  // card does not vanish out from under the click that created it.
  const appliedJobIds = new Set(
    (applications.data ?? []).map((item) => item.application.job_posting_id),
  );

  return (
    <section aria-labelledby="smart-apply-heading">
      <h2 id="smart-apply-heading" className="sr-only">
        Smart Apply recommendations
      </h2>
      <div className="space-y-3">
        {recommended.map((match) => (
          <HighMatchCard
            key={match.job.job_id}
            match={match}
            hasApplied={appliedJobIds.has(match.job.job_id)}
          />
        ))}
      </div>
    </section>
  );
}
