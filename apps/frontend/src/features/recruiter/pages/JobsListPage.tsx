import { ArrowRight, Briefcase, Plus, SearchX } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  Button,
  EmptyState,
  ErrorState,
  Input,
  Pagination,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableCellMono,
  TableHead,
  TableHeaderCell,
  TableRow,
  Tabs,
} from "@/components";
import { Surface } from "@/design/Surface";
import { DeadLetterBanner } from "@/features/jobs";

import type { Job, JobStatus } from "../api/jobsApi";
import { JobStatusBadge } from "../components/JobStatusBadge";
import { useJobs } from "../hooks/useJobs";

const PAGE_SIZE = 10;

const STATUS_TABS: { id: string; label: string; status: JobStatus | null }[] = [
  { id: "all", label: "All", status: null },
  { id: "draft", label: "Draft", status: "draft" },
  { id: "extracting", label: "Reading", status: "extracting" },
  { id: "awaiting_confirmation", label: "Needs confirmation", status: "awaiting_confirmation" },
  { id: "published", label: "Published", status: "published" },
  { id: "closed", label: "Closed", status: "closed" },
];

type SortKey = "created" | "title";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function daysRemaining(deadline: string | null): string {
  if (!deadline) return "—";
  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return "Passed";
  if (days === 0) return "Today";
  return `${days}d left`;
}

function jobMeta(job: Job): string {
  const parts = [job.job_type.replace(/_/g, " "), job.experience_level];
  if (job.is_remote) parts.push("Remote");
  else if (job.location) parts.push(job.location);
  return parts.join(" · ");
}

/**
 * Job postings — every role, with where it stands.
 *
 * The table is the desktop view (Phase 2 `Table`, sortable by title and
 * created date); below `md` the same rows render as the card list this page
 * always used, because a five-column table squeezed onto a phone is
 * unreadable and the `Table`'s own horizontal scroll hides the status — the
 * one column a recruiter scans for. Search matches title, location and job
 * type; the tabs filter by the backend's own status values, nothing renamed.
 * The list is newest-created first; the API returns no ordering guarantee,
 * so the sort is explicit and client-side.
 */
export function JobsListPage() {
  const jobs = useJobs();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("created");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const items = useMemo(() => {
    const data = jobs.data ?? [];
    const q = query.trim().toLowerCase();
    const active = STATUS_TABS.find((t) => t.id === tab);
    const filtered = data.filter((job) => {
      if (active?.status && job.status !== active.status) return false;
      if (
        q &&
        !`${job.title} ${job.location ?? ""} ${job.job_type.replace(/_/g, " ")}`
          .toLowerCase()
          .includes(q)
      )
        return false;
      return true;
    });
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) =>
      sortKey === "title"
        ? dir * a.title.localeCompare(b.title)
        : dir * (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    );
  }, [jobs.data, query, tab, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = items.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "title" ? "asc" : "desc");
    }
    setPage(1);
  };

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

  if (jobs.data && jobs.data.length === 0) {
    return (
      <div className="space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">Job postings</h1>
            <p className="mt-1 text-sm text-[var(--slate)]">
              Create a role, confirm what GroundTruth extracts, publish.
            </p>
          </div>
          <Link
            to="/recruiter/jobs/new"
            className="inline-flex items-center gap-2 rounded-[var(--r-sm)] bg-gt-electric px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gt-electric/90"
          >
            <Plus size={16} aria-hidden="true" /> New job
          </Link>
        </header>

        <DeadLetterBanner />

        <EmptyState
          icon={Briefcase}
          title="No job postings yet"
          description="Create your first job to start finding matched candidates."
        />
      </div>
    );
  }

  const counts = (status: JobStatus | null) =>
    jobs.data.filter((job) => status === null || job.status === status).length;

  const hasFilters = query.trim() !== "" || tab !== "all";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">Job postings</h1>
          <p className="mt-1 text-sm text-[var(--slate)]">
            Create a role, confirm what GroundTruth extracts, publish.
          </p>
        </div>
        {/* Its own route rather than an inline form: creation now ends in a
            confirmation step at another URL, and a flow that begins inside a
            list page and ends two navigations later has no back button that
            means anything. */}
        <Link
          to="/recruiter/jobs/new"
          className="inline-flex items-center gap-2 rounded-[var(--r-sm)] bg-gt-electric px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gt-electric/90"
        >
          <Plus size={16} aria-hidden="true" /> New job
        </Link>
      </header>

      <DeadLetterBanner />

      <div className="space-y-3">
        <Input
          label="Search jobs"
          type="search"
          placeholder="Job title, location, or type"
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
          title="No jobs match"
          description="Try a different search or status — your postings are still here."
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
            {items.length === 1 ? "job" : "jobs"}
          </p>

          {/* Desktop: the table. */}
          <Surface className="hidden md:block">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell
                    sort={sortKey === "title" ? sortDir : null}
                    onSort={() => toggleSort("title")}
                  >
                    Job
                  </TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell
                    sort={sortKey === "created" ? sortDir : null}
                    onSort={() => toggleSort("created")}
                  >
                    Created
                  </TableHeaderCell>
                  <TableHeaderCell>Deadline</TableHeaderCell>
                  <TableHeaderCell>
                    <span className="sr-only">Open</span>
                  </TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageItems.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>
                      <Link
                        to={`/recruiter/jobs/${job.id}`}
                        className="font-medium text-[var(--ink)] hover:underline"
                      >
                        {job.title}
                      </Link>
                      <p className="mt-0.5 text-xs text-[var(--slate)]">{jobMeta(job)}</p>
                    </TableCell>
                    <TableCell>
                      <JobStatusBadge status={job.status} />
                    </TableCell>
                    <TableCellMono>{formatDate(job.created_at)}</TableCellMono>
                    <TableCell className="whitespace-nowrap text-[var(--slate)]">
                      {daysRemaining(job.deadline)}
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/recruiter/jobs/${job.id}`}
                        aria-label={`Open ${job.title}`}
                        className="inline-flex items-center gap-1 text-sm font-medium text-gt-electric hover:underline"
                      >
                        Open
                        <ArrowRight size={14} aria-hidden="true" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Surface>

          {/* Mobile: the card list this page always used. */}
          <ul className="space-y-3 md:hidden">
            {pageItems.map((job) => (
              <li key={job.id}>
                <Link to={`/recruiter/jobs/${job.id}`}>
                  <Surface interactive className="flex items-center justify-between gap-4 p-5">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-[var(--ink)]">{job.title}</p>
                      <p className="mt-0.5 text-xs text-[var(--slate)]">{jobMeta(job)}</p>
                      <p className="mt-1.5 text-xs text-[var(--muted)]">
                        Created {formatDate(job.created_at)} · Deadline {daysRemaining(job.deadline)}
                      </p>
                    </div>
                    <JobStatusBadge status={job.status} />
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
