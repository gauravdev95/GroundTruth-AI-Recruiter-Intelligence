import { Surface } from "@/design/Surface";

import type { ApplicationListItem, ApplicationStatus } from "../api/applicationsApi";

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview",
  hired: "Hired",
  rejected: "Not selected",
};

/**
 * The overview strip: one count per pipeline status, plus the total.
 *
 * Every number is counted from the list this page already fetched — no
 * separate stats endpoint exists, and none is invented. The counts are
 * plain numbers in `--ink`: a count is not a status claim, so it spends no
 * status colour (tokens.css rule 1). The statuses themselves keep their
 * badge vocabulary on the list rows below.
 */
export function ApplicationStats({ items }: { items: ApplicationListItem[] }) {
  const counts: Record<ApplicationStatus, number> = {
    applied: 0,
    shortlisted: 0,
    interview_scheduled: 0,
    hired: 0,
    rejected: 0,
  };
  for (const item of items) counts[item.application.status] += 1;

  const stats: { label: string; value: number }[] = [
    { label: "Total applications", value: items.length },
    ...(Object.keys(STATUS_LABELS) as ApplicationStatus[]).map((status) => ({
      label: STATUS_LABELS[status],
      value: counts[status],
    })),
  ];

  return (
    <Surface className="px-2 py-4 sm:px-4">
      <dl className="grid grid-cols-2 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((stat) => (
          <div key={stat.label} className="px-4 text-center sm:text-left">
            <dd className="tabular font-display text-2xl font-semibold text-[var(--ink)]">
              {stat.value}
            </dd>
            <dt className="mt-0.5 text-xs text-[var(--muted)]">{stat.label}</dt>
          </div>
        ))}
      </dl>
    </Surface>
  );
}
