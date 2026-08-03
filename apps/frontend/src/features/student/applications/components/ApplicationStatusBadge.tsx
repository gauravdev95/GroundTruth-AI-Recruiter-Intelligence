import { Badge } from "@/components";

import type { ApplicationStatus } from "../api/applicationsApi";

const LABELS: Record<ApplicationStatus, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview scheduled",
  hired: "Hired",
  rejected: "Not selected",
};

const VARIANTS: Record<ApplicationStatus, "neutral" | "warning" | "success" | "danger" | "info"> = {
  applied: "info",
  shortlisted: "info",
  interview_scheduled: "warning",
  hired: "success",
  rejected: "danger",
};

export function ApplicationStatusBadge({ status }: { status: ApplicationStatus }) {
  return <Badge variant={VARIANTS[status]}>{LABELS[status]}</Badge>;
}
