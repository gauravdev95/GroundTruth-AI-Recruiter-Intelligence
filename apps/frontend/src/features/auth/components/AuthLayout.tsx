import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { Backdrop } from "@/design/Surface";

interface AuthLayoutProps {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}

function BrandMark() {
  return (
    <Link
      to="/"
      className="inline-flex items-center gap-2 text-[var(--ink)]"
      aria-label="GroundTruth — home"
    >
      <svg width="24" height="24" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path
          d="M10 9 L4 16 L10 23"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="square"
        />
        <path
          d="M22 9 L28 16 L22 23"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="square"
        />
        {/*
          The tick keeps `--verified` rather than `currentColor`. It is the
          product's one standing claim — "proven" — and the mark is the same
          mark on every surface; letting it inherit would turn it into a
          decorative flourish that happens to be green on some pages.
        */}
        <path
          d="M11.5 16.2 L15 19.6 L20.5 12"
          stroke="var(--verified)"
          strokeWidth="2.4"
          strokeLinecap="square"
        />
      </svg>
      <span className="font-display text-[15px] font-bold tracking-tight text-[var(--ink)]">
        GroundTruth
      </span>
    </Link>
  );
}

/**
 * The card layout behind `/forgot-password`, `/reset-password` and the OAuth
 * callback.
 *
 * This is the seam the auth rebuild left open: `/login` and `/signup` moved to
 * the dark `AuthHero`, and these three stayed on a white card with a
 * `#D3DAE3` blueprint grid, so "Forgot password?" walked you out of the
 * product's visual world. It is now on the same tokens as the rest of the app
 * and shares the app's ambient `Backdrop`, which is what makes the transition
 * out of the hero read as one product rather than two.
 *
 * It is deliberately NOT converted into `AuthHero`. The hero is a full-height
 * animated aurora sized for a page a first-time visitor lands on with intent;
 * a password reset is a two-field errand, and wrapping it in the same
 * production would make the smallest task in the product look like the
 * biggest. Same tokens, same backdrop, quieter form.
 */
export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen items-start justify-center bg-[var(--bg)] px-4 pb-12 pt-24 sm:pb-16 sm:pt-28">
      <Backdrop />

      {/* Hairline blueprint grid, carried over from the landing page. Drawn in
          `--rule` so it survives the theme; at #D3DAE3 it was invisible on the
          dark theme and too heavy on the light one. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-60 [background-image:linear-gradient(var(--rule)_1px,transparent_1px),linear-gradient(90deg,var(--rule)_1px,transparent_1px)] [background-size:64px_64px] [mask-image:radial-gradient(60%_55%_at_50%_45%,#000_20%,transparent_80%)]"
      />

      <div className="absolute left-6 top-6 sm:left-8 sm:top-8">
        <BrandMark />
      </div>

      <Link
        to="/"
        className="absolute right-6 top-6 inline-flex items-center gap-1.5 text-sm font-medium text-[var(--slate)] transition-colors hover:text-[var(--ink)] sm:right-8 sm:top-8"
      >
        <ArrowLeft size={15} aria-hidden="true" /> Back to home
      </Link>

      <div className="relative z-10 my-auto w-full max-w-md animate-scale-in">
        <div className="rounded-[var(--r-lg)] border border-[var(--rule)] bg-[var(--panel)] p-7 shadow-[var(--shadow-panel)] backdrop-blur-sm sm:p-9">
          <div className="mb-7 text-center">
            <h1 className="font-display text-2xl font-bold tracking-tight text-[var(--ink)]">
              {title}
            </h1>
            {subtitle ? <p className="mt-2 text-sm text-[var(--slate)]">{subtitle}</p> : null}
          </div>
          {children}
        </div>
        {footer ? (
          <div className="mt-6 text-center text-sm text-[var(--slate)]">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}
