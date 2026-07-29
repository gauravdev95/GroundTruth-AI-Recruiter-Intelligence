import { LayoutDashboard } from "lucide-react";

import { DashboardShell, type DashboardNavItem } from "@/components";
import { useAuthContext } from "@/features/auth";
import { useLogout } from "@/features/auth/hooks/useAuth";

const NAV_ITEMS: DashboardNavItem[] = [{ label: "Overview", icon: LayoutDashboard, to: "/candidate" }];

export function StudentDashboardLayout() {
  const { user } = useAuthContext();
  const logout = useLogout();

  return (
    <DashboardShell
      navItems={NAV_ITEMS}
      userName={user?.full_name ?? ""}
      userEmail={user?.email ?? ""}
      onLogout={() => logout.mutate()}
      isLoggingOut={logout.isPending}
    />
  );
}
