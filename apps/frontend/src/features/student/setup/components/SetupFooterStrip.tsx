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
    <div className="flex items-start gap-3 rounded-2xl border border-violet-100/80 bg-white/70 px-5 py-4">
      <ArrowLeftRight size={18} className="mt-0.5 shrink-0 text-violet-500" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-slate-700">
          You can switch between Resume Upload and Manual Entry at any time.
        </p>
        <p className="mt-0.5 text-xs text-slate-500">All your progress will be saved automatically.</p>
      </div>
      <ShieldCheck size={18} className="mt-0.5 shrink-0 text-violet-400" aria-hidden="true" />
    </div>
  );
}
