import { ChevronDown, LogOut, Menu, PanelLeftClose, PanelLeftOpen, UserRound, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Backdrop } from "@/design/Surface";
import { cn } from "@/lib/utils";

import { Dropdown, type DropdownEntry } from "./Dropdown";

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
  /** Rendered in the header, left of the user menu — the notification bell.
   * Optional so non-dashboard consumers of this shell aren't forced to wire
   * one in. */
  headerExtra?: ReactNode;
  /**
   * Collapse the desktop rail to icons only. Opt-in per dashboard: the
   * student dashboard offers it (long pages, small laptop screens); the
   * recruiter dashboard keeps the full rail until its own phase decides.
   * The choice persists in localStorage, not in state that resets per visit.
   */
  collapsible?: boolean;
  /** Where "Your profile" in the user menu goes. Absent, the menu is just
   * sign-out — a shell that does not know its own profile route must not
   * guess one. */
  profileHref?: string;
}

/**
 * Generic Sidebar + Topbar + user menu + responsive shell, shared by the
 * candidate (`features/student/`) and recruiter (`features/recruiter/`)
 * dashboards — role-specific nav items are passed in, content renders through
 * `<Outlet />` from whichever nested route matched.
 *
 * THIS IS WHERE THE APP'S SURFACE STACK IS ESTABLISHED, so the three levels it
 * uses are worth naming once:
 *
 *   --bg           the field the ambient `Backdrop` blooms sit on. Never
 *                  carries content directly.
 *   --surface      the chrome: rail and topbar. Opaque, because chrome that
 *                  lets content scroll visibly beneath it stops reading as
 *                  chrome.
 *   --panel        cards inside `<main>`, via `Surface`. Translucent, so the
 *                  backdrop passes through them.
 *
 * `Backdrop` is mounted here rather than per route precisely because it is
 * fixed: rendering it inside a route would restart its layer on every
 * navigation, and the blooms are the one thing on screen that should not
 * acknowledge that navigation happened.
 */
export function DashboardShell({
  navItems,
  userName,
  userEmail,
  onLogout,
  isLoggingOut,
  headerExtra,
  collapsible = false,
  profileHref,
}: DashboardShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  // Desktop-only; the mobile sheet is always full-width. Read lazily so a
  // stored choice applies on the first paint rather than after a re-render.
  const [railCollapsed, setRailCollapsed] = useState(
    () => collapsible && window.localStorage.getItem("gt:rail-collapsed") === "1",
  );

  function toggleRail() {
    setRailCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("gt:rail-collapsed", next ? "1" : "0");
      return next;
    });
  }

  /*
   * The sheet closes on navigation. Previously each NavLink closed it in its
   * own onClick, which missed every other way out of it — the logout button,
   * a browser back gesture, or a redirect fired by a query invalidation.
   */
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  /*
   * Escape closes the sheet, and the body does not scroll behind it. Both are
   * table stakes for something that covers the viewport, and neither was here
   * before; the sheet is `fixed inset-0`, so without the scroll lock a swipe
   * over the scrim moved the page underneath it.
   */
  useEffect(() => {
    if (!mobileNavOpen) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileNavOpen(false);
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [mobileNavOpen]);

  // One nav, two widths. The mobile sheet always renders the full labels;
  // the desktop rail hides them when collapsed, keeping the icon, the active
  // rail and a `title`/`aria-label` so the item is still identifiable.
  const renderNav = (collapsed: boolean) => (
    <nav className={cn("flex flex-1 flex-col gap-0.5 py-4", collapsed ? "items-center px-2" : "px-3")}>
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end
          title={collapsed ? item.label : undefined}
          aria-label={collapsed ? item.label : undefined}
          className={({ isActive }) =>
            cn(
              "relative flex items-center gap-3 rounded-[var(--r-sm)] py-2.5 text-sm font-medium",
              collapsed ? "justify-center px-2.5" : "px-3",
              "transition-colors duration-150",
              isActive
                ? /*
                   * The active item is marked twice: a filled panel and a
                   * violet rail on the leading edge. The rail is what survives
                   * a colour-vision difference and a low-contrast display,
                   * which a fill alone does not — and the rail, not the fill,
                   * is why the item reads as *current* rather than as hovered.
                   */
                  "bg-[var(--panel)] text-[var(--ink)]"
                : "text-[var(--slate)] hover:bg-[var(--panel)] hover:text-[var(--ink)]",
            )
          }
        >
          {({ isActive }) => (
            <>
              {isActive ? (
                <span
                  aria-hidden="true"
                  className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-[var(--violet)]"
                />
              ) : null}
              <item.icon size={18} aria-hidden="true" />
              {collapsed ? null : item.label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );

  const nav = renderNav(false);

  // The user menu: avatar trigger, profile link, sign-out. The old bare
  // logout icon is gone — a header action that ends the session deserves a
  // named menu item, and the avatar is where a signed-in user looks for one.
  const userMenuItems: DropdownEntry[] = [
    ...(profileHref
      ? [
          {
            id: "profile",
            label: "Your profile",
            icon: UserRound,
            onSelect: () => navigate(profileHref),
          } satisfies DropdownEntry,
        ]
      : []),
    ...(profileHref ? [{ type: "separator", id: "sep" } satisfies DropdownEntry] : []),
    {
      id: "logout",
      label: isLoggingOut ? "Signing out…" : "Sign out",
      icon: LogOut,
      danger: true,
      disabled: isLoggingOut,
      onSelect: onLogout,
    },
  ];

  const userMenu = (
    <Dropdown
      align="end"
      items={userMenuItems}
      trigger={(props) => (
        <button
          type="button"
          {...props}
          className="flex items-center gap-2 rounded-[var(--r-sm)] py-1 pl-1 pr-1.5 transition-colors hover:bg-[var(--panel)] sm:pr-2"
        >
          <span
            aria-hidden="true"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--violet)] text-sm font-semibold text-white"
          >
            {userName.slice(0, 1).toUpperCase() || "?"}
          </span>
          <span className="hidden text-right sm:block">
            <span className="block text-sm font-medium leading-tight text-[var(--ink)]">{userName}</span>
            <span className="block max-w-[12rem] truncate text-xs leading-tight text-[var(--muted)]">
              {userEmail}
            </span>
          </span>
          <ChevronDown size={15} className="hidden text-[var(--muted)] sm:block" aria-hidden="true" />
        </button>
      )}
    />
  );

  const brand = (
    <span className="font-display text-[15px] font-semibold tracking-tight text-[var(--ink)]">
      GroundTruth
    </span>
  );

  return (
    <div className="flex min-h-screen bg-[var(--bg)] text-[var(--ink)]">
      <Backdrop />

      {/* Sticky and viewport-tall, so the nav stays reachable on a long
          dashboard instead of scrolling off the top with the content. */}
      <aside
        className={cn(
          "sticky top-0 hidden h-screen flex-col border-r border-[var(--rule)] bg-[var(--surface)] transition-[width] duration-200 lg:flex",
          railCollapsed ? "w-16" : "w-[var(--rail-w)]",
        )}
      >
        <div
          className={cn(
            "flex h-[var(--nav-h)] shrink-0 items-center",
            railCollapsed ? "justify-center px-2" : "justify-between px-5",
          )}
        >
          {railCollapsed ? (
            <span
              aria-hidden="true"
              className="flex size-9 items-center justify-center rounded-[var(--r-sm)] bg-[var(--violet)] font-display text-base font-bold text-white"
            >
              G
            </span>
          ) : (
            brand
          )}
          {collapsible ? (
            <button
              type="button"
              onClick={toggleRail}
              aria-label={railCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={railCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="rounded-[var(--r-sm)] p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--panel)] hover:text-[var(--ink)]"
            >
              {railCollapsed ? (
                <PanelLeftOpen size={18} aria-hidden="true" />
              ) : (
                <PanelLeftClose size={18} aria-hidden="true" />
              )}
            </button>
          ) : null}
        </div>
        {renderNav(railCollapsed)}
      </aside>

      {mobileNavOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-[var(--scrim)] backdrop-blur-sm"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          {/* Opaque `--surface`, not `--panel`: a translucent sheet over
              arbitrary scrolled content is unreadable rather than airy. */}
          <aside className="relative flex h-full w-[var(--rail-w)] flex-col border-r border-[var(--rule)] bg-[var(--surface)] shadow-[var(--shadow-raised)]">
            <div className="flex h-[var(--nav-h)] items-center justify-between px-5">
              {brand}
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close menu"
                className="rounded-[var(--r-sm)] p-1 text-[var(--slate)] transition-colors hover:text-[var(--ink)]"
              >
                <X size={20} />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        {/*
          Sticky, and translucent with a blur — the one place in the app a real
          backdrop filter is worth its compositor layer, because there is
          exactly one of it on screen and content passes under it constantly.
          `Surface` deliberately refuses the same treatment for cards, where
          the cost is per-card. See the note in design/Surface.tsx.
        */}
        <header className="sticky top-0 z-30 flex h-[var(--nav-h)] items-center justify-between border-b border-[var(--rule)] bg-[var(--surface)]/85 px-4 backdrop-blur-md sm:px-6">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open menu"
            className="rounded-[var(--r-sm)] p-1 text-[var(--slate)] transition-colors hover:text-[var(--ink)] lg:hidden"
          >
            <Menu size={22} />
          </button>
          <div className="hidden lg:block" />
          <div className="flex items-center gap-1.5 sm:gap-3">
            {headerExtra}
            {userMenu}
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
