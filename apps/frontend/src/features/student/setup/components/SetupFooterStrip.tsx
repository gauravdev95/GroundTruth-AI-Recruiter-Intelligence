import { ArrowLeftRight, ShieldCheck } from "lucide-react";

/**
 * The reassurance strip under the two cards.
 *
 * It states a property the routing actually has: both paths are plain routes,
 * neither writes a one-way flag, and switching clears nothing. If that ever
 * stops being true, this copy is the thing that made it a promise.
 */
export function SetupFooterStrip() {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-[var(--violet)]/25 bg-[var(--panel)]/70 px-5 py-4">
      <ArrowLeftRight size={18} className="mt-0.5 shrink-0 text-[var(--violet)]" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-[var(--slate)]">
          You can switch between Resume Upload and Manual Entry at any time.
        </p>
        <p className="mt-0.5 text-xs text-[var(--slate)]">All your progress will be saved automatically.</p>
      </div>
      <ShieldCheck size={18} className="mt-0.5 shrink-0 text-[var(--violet)]" aria-hidden="true" />
    </div>
  );
}
