import { LayoutDashboard } from "lucide-react";

import { EmptyState } from "@/components";

/** Placeholder — proves the shell renders. Real candidate dashboard
 * content (profile, evidence, applications) is out of scope for this
 * phase; see `docs/DATA_MODEL.md` for the data these will eventually read. */
export function DashboardHome() {
  return (
    <EmptyState
      icon={LayoutDashboard}
      title="Your dashboard is on its way"
      description="Profile, evidence, and application tracking land in a future phase."
    />
  );
}
