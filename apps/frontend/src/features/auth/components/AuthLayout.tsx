import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

interface AuthLayoutProps {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}

function BrandMark() {
  return (
    <Link to="/" className="inline-flex items-center gap-2 text-ink" aria-label="GroundTruth — home">
      <svg width="24" height="24" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path d="M10 9 L4 16 L10 23" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square" />
        <path d="M22 9 L28 16 L22 23" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square" />
        <path
          d="M11.5 16.2 L15 19.6 L20.5 12"
          stroke="#0E7C55"
          strokeWidth="2.4"
          strokeLinecap="square"
        />
      </svg>
      <span className="font-display text-[15px] font-bold tracking-tight text-ink">
        GroundTruth
      </span>
    </Link>
  );
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen items-start justify-center bg-paper px-4 pb-12 pt-24 sm:pb-16 sm:pt-28">
      {/* Hairline blueprint grid, carried over from the landing page. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-70 [background-image:linear-gradient(#D3DAE3_1px,transparent_1px),linear-gradient(90deg,#D3DAE3_1px,transparent_1px)] [background-size:64px_64px] [mask-image:radial-gradient(60%_55%_at_50%_45%,#000_20%,transparent_80%)]"
      />

      <div className="absolute left-6 top-6 sm:left-8 sm:top-8">
        <BrandMark />
      </div>

      <Link
        to="/"
        className="absolute right-6 top-6 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-900 sm:right-8 sm:top-8"
      >
        <ArrowLeft size={15} /> Back to home
      </Link>

      <div className="relative z-10 my-auto w-full max-w-md animate-scale-in">
        <div className="rounded border border-rule bg-panel p-7 sm:p-9">
          <div className="mb-7 text-center">
            <h1 className="font-display text-2xl font-bold tracking-tight text-ink">{title}</h1>
            {subtitle ? <p className="mt-2 text-sm text-slate-500">{subtitle}</p> : null}
          </div>
          {children}
        </div>
        {footer ? <div className="mt-6 text-center text-sm text-slate-500">{footer}</div> : null}
      </div>
    </div>
  );
}
