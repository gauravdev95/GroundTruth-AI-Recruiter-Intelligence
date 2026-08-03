import { ClipboardList } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, Skeleton } from "@/components";

import { ApplicationStatusBadge } from "../components/ApplicationStatusBadge";
import { useMyApplications } from "../hooks/useApplications";

/** "My Applications" — stage plus the last time it changed, per application.
 * There's no full event-by-event history table in this schema
 * (`Application.status` + `status_updated_at` only), so "history" here is
 * the current stage and when it was last touched, not a timeline. */
export function MyApplicationsPage() {
  const applications = useMyApplications();

  if (applications.isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (applications.isError) {
    return <ErrorState title="Could not load your applications" description="Something went wrong." />;
  }

  if (applications.data.length === 0) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="No applications yet"
        description="Smart Apply to a matched job from your job feed and it will show up here."
      />
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold text-ink">My applications</h1>
        <p className="mt-1 text-sm text-slate-500">Track where each application stands.</p>
      </header>

      <ul className="space-y-3">
        {applications.data.map(({ application, job_title, company_name }) => (
          <li key={application.id}>
            <Link
              to={`/student/applications/${application.id}`}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rule bg-white p-5 transition hover:border-ink/30"
            >
              <div>
                <p className="font-medium text-ink">{job_title}</p>
                <p className="text-xs text-slate-500">{company_name}</p>
              </div>
              <div className="text-right">
                <ApplicationStatusBadge status={application.status} />
                <p className="mt-1.5 text-xs text-slate-400">
                  Updated {new Date(application.status_updated_at).toLocaleDateString()}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
