import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

import { useAuthContext } from "@/features/auth/context/AuthContext";

import { CTA, NAV, ROUTES } from "../content/landing";
import { SPRING, observeIntersection, useIsNarrow, useMagnetic, useReducedMotionSafe } from "../lib/motion";
import { Logo } from "./Logo";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * Hoisted so its identity is stable. Mapping this inline would hand
 * `useActiveSection` a new array on every render, tearing down and rebuilding
 * four IntersectionObserver registrations each time.
 */
const NAV_HREFS = NAV.links.map((link) => link.href);

/**
 * Which section the reader is currently in, for the nav's active underline.
 *
 * Uses the page's shared observer registry with a band around the viewport's
 * middle, so "active" means "crossing the centre of the screen" rather than
 * "touching an edge". When two sections qualify, the earlier one in document
 * order wins, which stops the indicator flickering between neighbours.
 */
function useActiveSection(hrefs: readonly string[]): string | null {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const stops: Array<() => void> = [];
    const visible = new Set<string>();

    for (const href of hrefs) {
      const element = document.getElementById(href.slice(1));
      if (!element) continue;

      stops.push(
        observeIntersection(
          element,
          (isIntersecting) => {
            if (isIntersecting) visible.add(href);
            else visible.delete(href);
            setActive(hrefs.find((candidate) => visible.has(candidate)) ?? null);
          },
          { rootMargin: "-45% 0px -45% 0px" },
        ),
      );
    }

    return () => stops.forEach((stop) => stop());
  }, [hrefs]);

  return active;
}

interface NavItemProps {
  href: string;
  label: string;
  active: boolean;
  reduced: boolean;
}

/**
 * A nav link with a small magnetic pull toward the pointer.
 *
 * Its own component purely so the hook can be called once per link without
 * calling hooks inside a loop. Displacement is capped at 4px — enough to feel
 * responsive, not enough to read as gelatinous — and the shared hook already
 * disables it on touch and under reduced motion.
 */
function NavItem({ href, label, active, reduced }: NavItemProps) {
  const ref = useMagnetic<HTMLAnchorElement>(4);

  return (
    <a href={href} ref={ref} aria-current={active ? "true" : undefined}>
      {label}
      {/*
        `layoutId` makes this one underline travel between links rather than two
        underlines crossfading. Under reduced motion the travel duration drops
        to zero, so it cuts to its new position instead of sliding.
      */}
      {active && (
        <motion.span
          className="nav-underline"
          layoutId="nav-underline"
          aria-hidden="true"
          transition={reduced ? { duration: 0 } : SPRING}
        />
      )}
    </a>
  );
}

interface NavSheetProps {
  open: boolean;
  onClose: () => void;
  signedIn: boolean;
  onLogout: () => void;
}

/**
 * The mobile menu, as a real focus-trapped dialog.
 *
 * Below 720px the desktop links and the primary CTA are `display: none`, which
 * would otherwise leave phone users with a wordmark and nothing else — no
 * navigation and no signup path. Escape closes it, Tab cycles inside it, the
 * body scroll is locked while it is open, and focus returns to whatever opened
 * it on close.
 *
 * `components/Modal.tsx` is not reused here despite implementing the same
 * behaviour: it is Tailwind-styled for the dashboard's visual world — large
 * radii, a heavy black shadow — and this page allows two shadows total and 4px
 * radii. Same behaviour, this page's clothes.
 */
function NavSheet({ open, onClose, signedIn, onLogout }: NavSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;

    triggerRef.current = document.activeElement;
    const sheet = sheetRef.current;
    const focusable = sheet?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    focusable?.[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !focusable || focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
      (triggerRef.current as HTMLElement | null)?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="nav-sheet-scrim"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div ref={sheetRef} className="nav-sheet" role="dialog" aria-modal="true" aria-label="Site navigation">
        <div className="nav-sheet-top">
          <Logo />
          <button type="button" className="nav-sheet-close" onClick={onClose} aria-label="Close menu">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 3 L13 13 M13 3 L3 13" stroke="currentColor" strokeWidth="1.4" fill="none" />
            </svg>
          </button>
        </div>

        <nav className="nav-sheet-links" aria-label="Sections">
          {NAV.links.map((link) => (
            <a key={link.href} href={link.href} onClick={onClose}>
              {link.label}
            </a>
          ))}
        </nav>

        <div className="nav-sheet-actions">
          {signedIn ? (
            <button type="button" className="btn btn-2" onClick={onLogout}>
              Log out
            </button>
          ) : (
            <>
              <Link className="btn" to={CTA.student.href} onClick={onClose}>
                {CTA.student.label}
              </Link>
              <Link className="btn btn-2" to={CTA.recruiter.href} onClick={onClose}>
                {CTA.recruiter.label}
              </Link>
              <Link className="nav-sheet-login" to="/login" onClick={onClose}>
                {NAV.loginLabel}
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * The navigation bar.
 *
 * Four links, one login, one primary CTA, and nothing else. It renders at first
 * paint with no entrance animation, stays a constant 70px, and never hides on
 * scroll-down: a bar that reacts to scrolling is a bar the reader has to track,
 * and this page already asks them to track a twelve-beat console.
 *
 * The bottom hairline is functional rather than decorative. The backdrop moves
 * behind a translucent bar, so without an explicit edge the nav's lower
 * boundary drifts in and out of visibility as a light field passes under it.
 */
export function Nav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout } = useAuthContext();
  const active = useActiveSection(NAV_HREFS);
  const narrow = useIsNarrow();
  const reduced = useReducedMotionSafe();

  // The sheet is a mobile affordance; widening past the breakpoint while it is
  // open would leave a modal covering a perfectly usable navbar.
  useEffect(() => {
    if (!narrow) setMenuOpen(false);
  }, [narrow]);

  const closeMenu = useCallback(() => setMenuOpen(false), []);

  return (
    <nav className="nav">
      <div className="wrap nav-in">
        <Logo />

        <div className="nav-links">
          {NAV.links.map((link) => (
            <NavItem
              key={link.href}
              href={link.href}
              label={link.label}
              active={active === link.href}
              reduced={reduced}
            />
          ))}
        </div>

        {user ? (
          <div className="nav-user">
            <span className="nav-user-name">
              Hi, <b>{user.full_name.split(" ")[0]}</b>
            </span>
            <button type="button" className="nav-logout" onClick={() => void logout()}>
              Log out
            </button>
          </div>
        ) : (
          <div className="nav-right">
            <Link className="nav-login" to={ROUTES.login}>
              {NAV.loginLabel}
            </Link>
            <Link className="btn nav-cta" to={CTA.student.href}>
              <span className="btn-label">{CTA.student.short}</span>
              <span className="btn-arrow" aria-hidden="true">
                →
              </span>
            </Link>
          </div>
        )}

        {/* Hairline burger, drawn inline to match every other icon on the page. */}
        <button
          type="button"
          className="nav-burger"
          aria-expanded={menuOpen}
          aria-controls="nav-sheet"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <svg width="20" height="14" viewBox="0 0 20 14" aria-hidden="true">
            <path d="M0 1 H20 M0 7 H20 M0 13 H14" stroke="currentColor" strokeWidth="1.4" fill="none" />
          </svg>
        </button>
      </div>

      <div id="nav-sheet">
        <NavSheet
          open={menuOpen}
          onClose={closeMenu}
          signedIn={Boolean(user)}
          onLogout={() => {
            closeMenu();
            void logout();
          }}
        />
      </div>
    </nav>
  );
}
