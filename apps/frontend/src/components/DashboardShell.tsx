import { LogOut, Menu, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

export interface DashboardNavItem {
  label: string;
  icon: LucideIcon;
  to: string;
}

export interface DashboardShellProps {
  navItems: DashboardNavItem[];
  userName: string;
  userEmail: string;
  onLogout: () => void;
  isLoggingOut?: boolean;
}

/** Generic Sidebar + Topbar + user menu + responsive shell, shared by the
 * candidate (`features/student/`) and recruiter (`features/recruiter/`)
 * dashboards — role-specific nav items are passed in, content renders
 * through `<Outlet />` from whichever nested route matched. */
export function DashboardShell({ navItems, userName, userEmail, onLogout, isLoggingOut }: DashboardShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const nav = (
    <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end
          onClick={() => setMobileNavOpen(false)}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
              isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
            )
          }
        >
          <item.icon size={18} />
          {item.label}
        </NavLink>
      ))}
    </nav>
  );

  const brand = (
    <span className="text-[15px] font-semibold tracking-tight text-slate-900">
      GroundTruth <span className="bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] bg-clip-text text-transparent">AI</span>
    </span>
  );

  return (
    <div className="flex min-h-screen bg-[#F6F7F9]">
      <aside className="hidden w-64 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-16 items-center px-5">{brand}</div>
        {nav}
      </aside>

      {mobileNavOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative flex h-full w-64 flex-col bg-white shadow-xl">
            <div className="flex h-16 items-center justify-between px-5">
              {brand}
              <button type="button" onClick={() => setMobileNavOpen(false)} aria-label="Close menu">
                <X size={20} className="text-slate-500" />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open menu"
            className="text-slate-500 lg:hidden"
          >
            <Menu size={22} />
          </button>
          <div className="hidden lg:block" />
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium text-slate-900">{userName}</div>
              <div className="text-xs text-slate-500">{userEmail}</div>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-sm font-semibold text-white">
              {userName.slice(0, 1).toUpperCase() || "?"}
            </div>
            <button
              type="button"
              onClick={onLogout}
              disabled={isLoggingOut}
              aria-label="Log out"
              title="Log out"
              className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-60"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
