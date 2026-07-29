import { LayoutDashboard } from "lucide-react";

import { EmptyState } from "@/components";

/** Placeholder — proves the shell renders. Real recruiter dashboard
 * content (job postings, candidate search, applications) is out of scope
 * for this phase; see `docs/DATA_MODEL.md` for the data these will
 * eventually read. */
export function DashboardHome() {
  return (
    <EmptyState
      icon={LayoutDashboard}
      title="Your dashboard is on its way"
      description="Job postings, candidate search, and applications land in a future phase."
    />
  );
}
