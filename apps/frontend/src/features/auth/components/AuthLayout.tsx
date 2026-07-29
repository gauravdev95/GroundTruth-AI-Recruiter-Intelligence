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
    <Link to="/" className="inline-flex items-center gap-2 text-white/90" aria-label="GroundTruth AI — home">
      <svg width="24" height="24" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path
          d="M10 9 L4 16 L10 23"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M22 9 L28 16 L22 23"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M11.5 16.2 L15 19.6 L20.5 12"
          stroke="url(#authg)"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="11.5" cy="16.2" r="1.5" fill="url(#authg)" />
        <defs>
          <linearGradient id="authg" x1="11" y1="20" x2="21" y2="12" gradientUnits="userSpaceOnUse">
            <stop stopColor="#5E8BFF" />
            <stop offset="1" stopColor="#9B6BFF" />
          </linearGradient>
        </defs>
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-slate-900">
        GroundTruth <span className="bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] bg-clip-text text-transparent">AI</span>
      </span>
    </Link>
  );
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#F6F7F9] px-4 py-10 sm:py-16">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-96 w-96 animate-float rounded-full bg-indigo-400/20 blur-3xl" />
        <div
          className="absolute -bottom-40 -right-40 h-96 w-96 animate-float rounded-full bg-violet-400/20 blur-3xl"
          style={{ animationDelay: "-3s" }}
        />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(79,70,229,0.06),transparent_60%)]" />
      </div>

      <div className="absolute left-6 top-6 sm:left-8 sm:top-8">
        <BrandMark />
      </div>

      <Link
        to="/"
        className="absolute right-6 top-6 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-900 sm:right-8 sm:top-8"
      >
        <ArrowLeft size={15} /> Back to home
      </Link>

      <div className="relative z-10 w-full max-w-md animate-scale-in">
        <div className="rounded-3xl border border-slate-200 bg-white/90 p-7 shadow-xl shadow-slate-900/5 backdrop-blur-xl sm:p-9">
          <div className="mb-7 text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
            {subtitle ? <p className="mt-2 text-sm text-slate-500">{subtitle}</p> : null}
          </div>
          {children}
        </div>
        {footer ? <div className="mt-6 text-center text-sm text-slate-500">{footer}</div> : null}
      </div>
    </div>
  );
}
