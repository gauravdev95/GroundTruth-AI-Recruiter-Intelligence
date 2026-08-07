import { ChevronDown, HelpCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useAuthContext } from "@/features/auth";
import { useLogout } from "@/features/auth/hooks/useAuth";

/** Initials for the avatar. Two letters at most — three-word names would
 * otherwise overflow the circle. */
function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/**
 * The setup flow's own chrome.
 *
 * Deliberately not `DashboardShell`: this screen runs *before* the student has
 * a profile worth navigating, and the shell's sidebar would offer five
 * destinations that are all either empty or gated. A student mid-setup should
 * see one path forward, not a menu.
 */
export function SetupTopBar() {
  const { user } = useAuthContext();
  const logout = useLogout();
  const [isMenuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isMenuOpen) return;

    function onPointerDown(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isMenuOpen]);

  const name = user?.full_name ?? "";

  return (
    <header className="border-b border-[var(--violet)]/25 bg-[var(--panel)]/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link to="/student/profile/setup" className="flex items-center gap-3 rounded-lg">
          <span
            aria-hidden="true"
            className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--violet)] to-[var(--blue)] font-display text-lg font-bold text-white shadow-sm shadow-[var(--shadow-panel)]"
          >
            G
          </span>
          <span className="min-w-0">
            <span className="block font-display text-base font-semibold leading-tight text-[var(--ink)]">
              GroundTruth
            </span>
            <span className="block text-[11px] leading-tight text-[var(--slate)]">
              AI Verified Talent Marketplace
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-2 sm:gap-4">
          <a
            href="mailto:support@groundtruth.dev?subject=Help%20with%20profile%20setup"
            className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm font-medium text-[var(--slate)] transition hover:bg-[var(--violet)]/10 hover:text-[var(--violet)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--violet)]"
          >
            <HelpCircle size={16} aria-hidden="true" />
            <span className="hidden sm:inline">Need Help?</span>
            <span className="sr-only sm:hidden">Need help</span>
          </a>

          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={isMenuOpen}
              className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 transition hover:bg-[var(--violet)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--violet)]"
            >
              <span
                aria-hidden="true"
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[var(--violet)] to-[var(--blue)] text-xs font-bold text-white"
              >
                {initials(name)}
              </span>
              <span className="hidden max-w-[9rem] truncate text-sm font-medium text-[var(--slate)] sm:block">
                {name}
              </span>
              <ChevronDown size={16} className="text-[var(--muted)]" aria-hidden="true" />
            </button>

            {isMenuOpen ? (
              <div
                role="menu"
                className="absolute right-0 z-20 mt-2 w-56 origin-top-right animate-scale-in rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-1.5 shadow-lg"
              >
                <p className="truncate px-2.5 py-1.5 text-xs text-[var(--slate)]">{user?.email}</p>
                <Link
                  role="menuitem"
                  to="/student/dashboard"
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-lg px-2.5 py-2 text-sm text-[var(--slate)] transition hover:bg-[var(--panel-raised)]"
                >
                  Go to dashboard
                </Link>
                <button
                  role="menuitem"
                  type="button"
                  onClick={() => logout.mutate()}
                  disabled={logout.isPending}
                  className="block w-full rounded-lg px-2.5 py-2 text-left text-sm text-[var(--slate)] transition hover:bg-[var(--panel-raised)] disabled:opacity-60"
                >
                  {logout.isPending ? "Signing out…" : "Sign out"}
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}
