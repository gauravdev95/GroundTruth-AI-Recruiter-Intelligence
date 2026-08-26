import { BarChart3, Briefcase, LayoutDashboard } from "lucide-react";

import { DashboardShell, type DashboardNavItem } from "@/components";
import { useAuthContext } from "@/features/auth";
import { useLogout } from "@/features/auth/hooks/useAuth";
import { NotificationBell } from "@/features/notifications";
import { useRealtimeEvents } from "@/features/realtime";

const NAV_ITEMS: DashboardNavItem[] = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/recruiter/dashboard" },
  { label: "Job postings", icon: Briefcase, to: "/recruiter/jobs" },
  { label: "Analytics", icon: BarChart3, to: "/recruiter/analytics" },
];

export function RecruiterDashboardLayout() {
  const { user } = useAuthContext();
  const logout = useLogout();

  // Subscribed at the layout so the socket survives navigation within the
  // recruiter area and the notification bell updates live.
  useRealtimeEvents();

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
