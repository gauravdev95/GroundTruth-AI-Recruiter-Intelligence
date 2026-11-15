import { ClipboardList, SearchX } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Button, EmptyState, ErrorState, Input, Pagination, Skeleton, Tabs } from "@/components";
import { Surface } from "@/design/Surface";

import type { ApplicationStatus } from "../api/applicationsApi";
import { ApplicationStats } from "../components/ApplicationStats";
import { ApplicationStatusBadge } from "../components/ApplicationStatusBadge";
import { useMyApplications } from "../hooks/useApplications";

const PAGE_SIZE = 10;

const STATUS_TABS: { id: string; label: string; status: ApplicationStatus | null }[] = [
  { id: "all", label: "All", status: null },
  { id: "applied", label: "Applied", status: "applied" },
  { id: "shortlisted", label: "Shortlisted", status: "shortlisted" },
  { id: "interview_scheduled", label: "Interview", status: "interview_scheduled" },
  { id: "hired", label: "Hired", status: "hired" },
  { id: "rejected", label: "Not selected", status: "rejected" },
];

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * "My Applications" — every Smart Apply, with where it stands.
 *
 * The statistics are counted from this same list (there is no stats
 * endpoint), the search matches job title and company, and the tabs filter
 * by the backend's own status values — nothing is renamed, and no stage
 * is invented. The list is newest-applied first; the API returns no
 * ordering guarantee, so the sort is explicit and client-side.
 *
 * There is no full event-by-event history in this schema
 * (`Application.status` + `status_updated_at` only), so "history" on the
 * detail page is the stage timeline derived from the current status — not
 * a log of past transitions.
 */
export function MyApplicationsPage() {
  const applications = useMyApplications();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("all");
  const [page, setPage] = useState(1);

  const items = useMemo(() => {
    const data = applications.data ?? [];
    const q = query.trim().toLowerCase();
    const active = STATUS_TABS.find((t) => t.id === tab);
    return data
      .filter((item) => {
        if (active?.status && item.application.status !== active.status) return false;
        if (q && !`${item.job_title} ${item.company_name}`.toLowerCase().includes(q))
          return false;
        return true;
      })
      .sort(
        (a, b) =>
          new Date(b.application.applied_at).getTime() -
          new Date(a.application.applied_at).getTime(),
      );
  }, [applications.data, query, tab]);

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = items.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  if (applications.isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (applications.isError) {
    return (
      <ErrorState
        title="Could not load your applications"
        description="Something went wrong while fetching your applications."
        action={
          <Button variant="secondary" onClick={() => void applications.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  if (applications.data.length === 0) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">My applications</h1>
          <p className="mt-1 text-sm text-[var(--slate)]">Track where each application stands.</p>
        </header>
        <EmptyState
          icon={ClipboardList}
          title="No applications yet"
          description="Smart Apply to a matched job from your job feed and it will show up here."
          action={
            <Link
              to="/student/matches"
              className="text-sm font-medium text-[var(--ink)] hover:underline"
            >
              Browse your job matches →
            </Link>
          }
        />
      </div>
    );
  }

  const counts = (status: ApplicationStatus | null) =>
    applications.data.filter((item) => status === null || item.application.status === status)
      .length;

  const hasFilters = query.trim() !== "" || tab !== "all";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">My applications</h1>
        <p className="mt-1 text-sm text-[var(--slate)]">Track where each application stands.</p>
      </header>

      <ApplicationStats items={applications.data} />

      <div className="space-y-3">
        <Input
          label="Search applications"
          type="search"
          placeholder="Job title or company"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(1);
          }}
        />
        <div className="overflow-x-auto">
          <Tabs
            value={tab}
            onChange={(id) => {
              setTab(id);
              setPage(1);
            }}
            tabs={STATUS_TABS.map((t) => ({
              id: t.id,
              label: t.label,
              count: counts(t.status),
            }))}
          />
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No applications match"
          description="Try a different search or status — your applications are still here."
          action={
            hasFilters ? (
              <Button
                variant="secondary"
                onClick={() => {
                  setQuery("");
                  setTab("all");
                  setPage(1);
                }}
              >
                Clear search and filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <p className="text-sm text-[var(--slate)]" aria-live="polite">
            <span className="tabular font-medium text-[var(--ink)]">{items.length}</span>{" "}
            {items.length === 1 ? "application" : "applications"}
          </p>

          <ul className="space-y-3">
            {pageItems.map(({ application, job_title, company_name }) => (
              <li key={application.id}>
                <Link to={`/student/applications/${application.id}`}>
                  <Surface
                    interactive
                    className="flex flex-wrap items-center justify-between gap-3 p-5"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-[var(--ink)]">{job_title}</p>
                      <p className="mt-0.5 text-xs text-[var(--slate)]">{company_name}</p>
                      <p className="mt-1.5 text-xs text-[var(--muted)]">
                        Applied {formatDate(application.applied_at)}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <ApplicationStatusBadge status={application.status} />
                      <p className="mt-1.5 text-xs text-[var(--muted)]">
                        Updated {formatDate(application.status_updated_at)}
                      </p>
                    </div>
                  </Surface>
                </Link>
              </li>
            ))}
          </ul>

          <div className="flex justify-center">
            <Pagination page={currentPage} totalPages={totalPages} onChange={setPage} />
          </div>
        </>
      )}
    </div>
  );
}
