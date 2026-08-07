import { authApi, type UserRole } from "../api/authApi";
import type { FieldTone } from "./fieldTone";

interface GoogleButtonProps {
  role: UserRole;
  label?: string;
  /** Which surface this sits on. See `fieldTone.ts`. */
  tone?: FieldTone;
}

/**
 * The Google mark keeps its four brand colours on both tones — Google's brand
 * guidelines require it, and a monochrome version to "fit the dark theme"
 * would be a trademark problem, not a design choice. Only the surface around
 * it changes.
 */
export function GoogleButton({ role, label = "Continue with Google", tone = "app" }: GoogleButtonProps) {
  return (
    <a
      href={authApi.googleLoginUrl(role)}
      className={
        tone === "hero"
          ? [
              "group flex w-full items-center justify-center gap-3 rounded-lg border border-white/15",
              "bg-white/[0.06] px-4 py-3 text-sm font-medium text-white backdrop-blur-sm",
              "transition-[transform,background-color,border-color] duration-200 ease-out",
              "hover:border-white/30 hover:bg-white/[0.11] motion-safe:hover:-translate-y-0.5",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric/50",
            ].join(" ")
          : "flex w-full items-center justify-center gap-3 rounded-[var(--r-md)] border border-[var(--rule)] bg-[var(--panel)] px-4 py-2.5 text-sm font-medium text-[var(--ink)] transition-colors hover:border-[var(--violet)]/50 hover:bg-[var(--panel-raised)]"
      }
    >
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.87 2.7-6.62z"
        />
        <path
          fill="#34A853"
          d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.95v2.33A9 9 0 0 0 9 18z"
        />
        <path
          fill="#FBBC05"
          d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.95A9 9 0 0 0 0 9c0 1.45.35 2.83.95 4.03l3-2.33z"
        />
        <path
          fill="#EA4335"
          d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .95 4.97l3 2.33C4.66 5.17 6.65 3.58 9 3.58z"
        />
      </svg>
      {label}
    </a>
  );
}
