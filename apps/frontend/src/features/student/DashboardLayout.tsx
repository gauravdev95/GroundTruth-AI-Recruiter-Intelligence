import { Briefcase, ClipboardList, FileUp, LayoutDashboard, UserRoundPen } from "lucide-react";

import { DashboardShell, type DashboardNavItem } from "@/components";
import { useAuthContext } from "@/features/auth";
import { useLogout } from "@/features/auth/hooks/useAuth";
import { NotificationBell } from "@/features/notifications";
import { useRealtimeEvents } from "@/features/realtime";

const NAV_ITEMS: DashboardNavItem[] = [
  { label: "Overview", icon: LayoutDashboard, to: "/student/dashboard" },
  { label: "Profile", icon: UserRoundPen, to: "/student/profile" },
  { label: "Import resume", icon: FileUp, to: "/student/resume" },
  { label: "Job matches", icon: Briefcase, to: "/student/matches" },
  { label: "My applications", icon: ClipboardList, to: "/student/applications" },
];

export function StudentDashboardLayout() {
  const { user } = useAuthContext();
  const logout = useLogout();

  // Subscribed at the layout, not on the dashboard home page: the socket
  // should survive navigation *within* the student area — a match arriving
  // while the student is on /student/matches has to land there too — and one
  // connection for the whole area beats opening and closing one per route.
  useRealtimeEvents();

  return (
    <DashboardShell
      navItems={NAV_ITEMS}
      userName={user?.full_name ?? ""}
      userEmail={user?.email ?? ""}
      onLogout={() => logout.mutate()}
      isLoggingOut={logout.isPending}
      headerExtra={<NotificationBell applicationHref={(id) => `/student/applications/${id}`} />}
    />
  );
}
