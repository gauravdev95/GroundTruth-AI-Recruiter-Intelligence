import { BarChart3, Briefcase } from "lucide-react";

import { DashboardShell, type DashboardNavItem } from "@/components";
import { useAuthContext } from "@/features/auth";
import { useLogout } from "@/features/auth/hooks/useAuth";
import { NotificationBell } from "@/features/notifications";

const NAV_ITEMS: DashboardNavItem[] = [
  { label: "Job postings", icon: Briefcase, to: "/recruiter/jobs" },
  { label: "Analytics", icon: BarChart3, to: "/recruiter/analytics" },
];

export function RecruiterDashboardLayout() {
  const { user } = useAuthContext();
  const logout = useLogout();

  return (
    <DashboardShell
      navItems={NAV_ITEMS}
      userName={user?.full_name ?? ""}
      userEmail={user?.email ?? ""}
      onLogout={() => logout.mutate()}
      isLoggingOut={logout.isPending}
      headerExtra={<NotificationBell applicationHref={(id) => `/recruiter/applications/${id}`} />}
    />
  );
}
