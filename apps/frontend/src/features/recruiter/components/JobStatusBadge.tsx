import { Badge } from "@/components";

import type { JobStatus } from "../api/jobsApi";

const LABELS: Record<JobStatus, string> = {
  draft: "Draft",
  extracting: "Reading description…",
  awaiting_confirmation: "Needs confirmation",
  published: "Published",
  closed: "Closed",
};

const VARIANTS: Record<JobStatus, "neutral" | "warning" | "success" | "danger" | "info"> = {
  draft: "neutral",
  extracting: "info",
  awaiting_confirmation: "warning",
  published: "success",
  closed: "neutral",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <Badge variant={VARIANTS[status]}>{LABELS[status]}</Badge>;
}
