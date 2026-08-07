import { Briefcase, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { Button, EmptyState, ErrorState, Skeleton } from "@/components";
import { DeadLetterBanner } from "@/features/jobs";

import { JobStatusBadge } from "../components/JobStatusBadge";
import { useJobs } from "../hooks/useJobs";

export function JobsListPage() {
  const jobs = useJobs();

  if (jobs.isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (jobs.isError) {
    return (
      <ErrorState
        title="Could not load your job postings"
        description="Something went wrong."
        action={
          <Button type="button" variant="secondary" size="sm" onClick={() => void jobs.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">Job postings</h1>
          <p className="mt-1 text-sm text-[var(--slate)]">Create a role, confirm what GroundTruth extracts, publish.</p>
        </div>
        {/* Its own route rather than an inline form: creation now ends in a
            confirmation step at another URL, and a flow that begins inside a
            list page and ends two navigations later has no back button that
            means anything. */}
        <Link
          to="/recruiter/jobs/new"
          className="inline-flex items-center gap-2 rounded bg-gt-electric px-4 py-2.5 text-sm font-bold text-white transition hover:bg-gt-electric/90"
        >
          <Plus size={16} aria-hidden="true" /> New job
        </Link>
      </header>

      <DeadLetterBanner />

      {jobs.data && jobs.data.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No job postings yet"
          description="Create your first job to start finding matched candidates."
        />
      ) : null}

      <ul className="space-y-3">
        {jobs.data?.map((job) => (
          <li key={job.id}>
            <Link
              to={`/recruiter/jobs/${job.id}`}
              className="flex items-center justify-between gap-4 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5 transition hover:border-[var(--rule)]"
            >
              <div>
                <p className="font-medium text-[var(--ink)]">{job.title}</p>
                <p className="mt-0.5 text-xs text-[var(--slate)]">
                  {job.job_type.replace("_", " ")} · {job.experience_level}
                  {job.location ? ` · ${job.location}` : job.is_remote ? " · Remote" : ""}
                </p>
              </div>
              <JobStatusBadge status={job.status} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
